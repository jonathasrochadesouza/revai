"""Marketplace integration for skills.sh — the open agent-skills directory.

Three upstream services, in order of reliance:

* ``skills.sh/api/search`` — the only stable JSON endpoint; returns id, name,
  source repo and install counts. No descriptions.
* ``raw.githubusercontent.com`` — the skill content itself, resolved through
  the standard SKILL.md layouts before anything else.
* ``api.github.com`` — recursive tree listing, used only when no candidate
  layout matches (e.g. catalog layouts like ``skills/<category>/<id>/``). It is
  rate-limited (60 req/h unauthenticated), which is why raw candidates run
  first and every resolution is cached.

Design rules:

* **Read-only.** Nothing is published, tracked or attributed back to the
  marketplace; the app behaves like a browser, not a client of record.
* **Fail soft on descriptions.** A gallery renders even when hydration is
  rate-limited or offline — name, source and installs come from the search
  endpoint; the description is best-effort.
* **Short-lived caches.** Marketplace views are disposable; the durable copy
  of a skill is the pinned content stored at install time.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import httpx
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from revai.domain.skills import SKILL_ID_PATTERN, SOURCE_PATTERN
from revai.errors import RevaiError

logger = logging.getLogger(__name__)

SEARCH_URL = "https://skills.sh/api/search"
RAW_BASE = "https://raw.githubusercontent.com"
GITHUB_API_BASE = "https://api.github.com"

SEARCH_TIMEOUT_S = 15.0
CONTENT_TIMEOUT_S = 20.0
CACHE_TTL_S = 600.0  # 10 minutes — long enough to de-dup a browsing session.
TREE_TTL_S = 3600.0  # 1 hour — repo layouts rarely change mid-session.
HYDRATION_CONCURRENCY = 6
MAX_SKILL_FILE_BYTES = 400_000

# Standard container layouts the skills CLI walks, most-specific first. The
# root SKILL.md comes last: a repo-level skill is rarer than a directory of
# them.
_SKILL_PATH_CANDIDATES = (
    "skills/{skill_id}/SKILL.md",
    "skills/.curated/{skill_id}/SKILL.md",
    "skills/.experimental/{skill_id}/SKILL.md",
    "skills/.system/{skill_id}/SKILL.md",
    ".claude/skills/{skill_id}/SKILL.md",
    ".agents/skills/{skill_id}/SKILL.md",
    "{skill_id}/SKILL.md",
    "SKILL.md",
)


class MarketplaceError(RevaiError):
    """A marketplace lookup failed with a user-actionable, keyed error."""


@dataclass
class MarketplaceSkill:
    """One row of a search result — the marketplace view of a skill."""

    id: str
    name: str
    source: str
    installs: int | None = None
    description: str = ""
    url: str = ""


@dataclass
class SkillContent:
    """The resolved content of one skill, ready to be pinned at install."""

    skill_id: str
    source: str
    name: str
    description: str
    body: str
    content_sha256: str
    license: str | None
    path: str
    source_url: str


@dataclass
class _CacheEntry:
    value: Any
    expires_at: float


@dataclass
class _TTLCache:
    ttl_s: float
    entries: dict[str, _CacheEntry] = field(default_factory=dict)

    def get(self, key: str) -> Any | None:
        entry = self.entries.get(key)
        if entry is None or entry.expires_at < time.monotonic():
            return None
        return entry.value

    def put(self, key: str, value: Any) -> None:
        self.entries[key] = _CacheEntry(value, time.monotonic() + self.ttl_s)


def _split_identity(source: str, skill_id: str) -> tuple[str, str]:
    """Validate and normalise the ``owner/repo`` + ``skill-id`` pair."""
    source = source.strip().strip("/")
    skill_id = skill_id.strip()
    if not SOURCE_PATTERN.fullmatch(source):
        raise MarketplaceError(422, "skill.invalid_source", {"source": source})
    if not SKILL_ID_PATTERN.fullmatch(skill_id):
        raise MarketplaceError(422, "skill.invalid_id", {"skill_id": skill_id})
    return source, skill_id


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Split a SKILL.md into its frontmatter mapping and the body below it."""
    stripped = text.strip()
    if not stripped.startswith("---"):
        return {}, text
    end = stripped.find("\n---", 3)
    if end < 0:
        return {}, text
    header = stripped[3:end]
    body_start = stripped.find("\n", end + 1)
    body = stripped[body_start + 1 :] if body_start >= 0 else ""
    try:
        data = YAML(typ="safe").load(header) or {}
    except YAMLError as exc:
        logger.debug("unparsable SKILL.md frontmatter: %s", exc)
        return {}, text
    if not isinstance(data, dict):
        return {}, text
    return data, body


class MarketplaceClient:
    """Fetches the marketplace catalog and skill content over HTTPS."""

    def __init__(self) -> None:
        self._search_cache = _TTLCache(CACHE_TTL_S)
        self._content_cache = _TTLCache(CACHE_TTL_S)
        self._tree_cache = _TTLCache(TREE_TTL_S)
        self._rate_limited_until = 0.0

    # -- public API -----------------------------------------------------------

    async def search(self, query: str, *, limit: int = 24) -> list[MarketplaceSkill]:
        """Search skills.sh, then hydrate descriptions from the skill sources."""
        query = query.strip()
        if len(query) < 2:
            raise MarketplaceError(422, "skill.query_too_short", {"query": query})

        cache_key = f"{query.casefold()}|{limit}"
        cached = self._search_cache.get(cache_key)
        if cached is not None:
            return cached

        self._raise_if_rate_limited()
        rows = await self._search_raw(query, limit)
        results: list[MarketplaceSkill] = []
        for item in rows:
            search_id = str(item.get("id") or "")
            parts = search_id.split("/")
            if len(parts) < 3:
                continue
            source, skill_id = "/".join(parts[:-1]), parts[-1]
            try:
                _split_identity(source, skill_id)
            except MarketplaceError:
                continue
            installs = item.get("installs")
            results.append(
                MarketplaceSkill(
                    id=skill_id,
                    name=str(item.get("name") or skill_id)[:200],
                    source=source,
                    installs=installs if isinstance(installs, int) else None,
                    url=f"https://skills.sh/skill/{search_id}",
                )
            )
        results.sort(key=lambda skill: (-(skill.installs or 0), skill.id))
        await self._hydrate_descriptions(results)
        self._search_cache.put(cache_key, results)
        return results

    async def content(self, source: str, skill_id: str) -> SkillContent:
        """Resolve, fetch and return one skill's SKILL.md content."""
        source, skill_id = _split_identity(source, skill_id)
        self._raise_if_rate_limited()
        return await self._content_for(source, skill_id)

    # -- skills.sh search -------------------------------------------------------

    async def _search_raw(self, query: str, limit: int) -> list[dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=SEARCH_TIMEOUT_S, follow_redirects=True) as client:
                response = await client.get(SEARCH_URL, params={"q": query, "limit": limit})
        except httpx.HTTPError as exc:
            logger.info("skills.sh search unreachable: %s", exc)
            raise MarketplaceError(503, "skill.marketplace_unavailable", {}) from exc
        if response.status_code == 429:
            self._rate_limited_until = time.monotonic() + 60
            raise MarketplaceError(429, "skill.marketplace_rate_limited", {"retry_after_s": 60})
        if response.status_code != 200:
            raise MarketplaceError(
                503, "skill.marketplace_unavailable", {"status_code": response.status_code}
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise MarketplaceError(503, "skill.marketplace_unavailable", {}) from exc
        skills = payload.get("skills")
        if not isinstance(skills, list):
            raise MarketplaceError(503, "skill.marketplace_unavailable", {})
        return [item for item in skills if isinstance(item, dict) and "id" in item]

    async def _hydrate_descriptions(self, results: list[MarketplaceSkill]) -> None:
        """Fill in descriptions concurrently; any failure leaves them empty."""
        semaphore = asyncio.Semaphore(HYDRATION_CONCURRENCY)

        async def hydrate(skill: MarketplaceSkill) -> None:
            async with semaphore:
                try:
                    content = await self._content_for(skill.source, skill.id)
                except RevaiError as exc:
                    logger.debug("description hydration skipped for %s: %s", skill.id, exc)
                    return
                skill.description = content.description

        await asyncio.gather(*(hydrate(skill) for skill in results))

    # -- content resolution ------------------------------------------------------

    async def _content_for(self, source: str, skill_id: str) -> SkillContent:
        cached = self._content_cache.get(f"{source}|{skill_id}")
        if cached is not None:
            return cached
        path = await self._resolve_path(source, skill_id)
        text = await self._fetch_text(f"{RAW_BASE}/{source}/HEAD/{path}")
        content = self._to_content(source, skill_id, path, text)
        self._content_cache.put(f"{source}|{skill_id}", content)
        return content

    async def _resolve_path(self, source: str, skill_id: str) -> str:
        """Find the SKILL.md path for a skill inside its source repository.

        Strategy, cheapest first: one raw probe of the most common layout,
        then (only if it misses) a single recursive tree listing that resolves
        the exact path — including catalog layouts like
        ``skills/<category>/<id>/SKILL.md`` — then, as a last resort, the
        remaining standard layouts for repos that keep a lone root SKILL.md.
        """
        cache_key = f"path|{source}|{skill_id}"
        cached = self._tree_cache.get(cache_key)
        if cached is not None:
            return cached

        first = _SKILL_PATH_CANDIDATES[0].format(skill_id=skill_id)
        probed = await self._probe_text(f"{RAW_BASE}/{source}/HEAD/{first}")
        if probed is not None:
            self._tree_cache.put(cache_key, first)
            self._content_cache.put(
                f"{source}|{skill_id}", self._to_content(source, skill_id, first, probed)
            )
            return first

        listing = await self._repo_tree(source)
        suffix = f"/{skill_id}/SKILL.md"
        matches = [path for path in listing if path.endswith(suffix)]
        if matches:
            # Shallowest path wins — the same shadowing rule the skills CLI
            # applies when a SKILL.md appears at several depths.
            best = min(matches, key=lambda path: (path.count("/"), len(path)))
            self._tree_cache.put(cache_key, best)
            return best

        for candidate in _SKILL_PATH_CANDIDATES[1:]:
            path = candidate.format(skill_id=skill_id)
            probed = await self._probe_text(f"{RAW_BASE}/{source}/HEAD/{path}")
            if probed is not None:
                self._tree_cache.put(cache_key, path)
                self._content_cache.put(
                    f"{source}|{skill_id}", self._to_content(source, skill_id, path, probed)
                )
                return path

        raise MarketplaceError(
            404, "skill.not_found_in_source", {"skill_id": skill_id, "source": source}
        )

    async def _repo_tree(self, source: str) -> list[str]:
        cache_key = f"tree|{source}"
        cached = self._tree_cache.get(cache_key)
        if cached is not None:
            return cached
        try:
            async with httpx.AsyncClient(timeout=CONTENT_TIMEOUT_S) as client:
                repo = await client.get(f"{GITHUB_API_BASE}/repos/{source}")
                if repo.status_code == 404:
                    raise MarketplaceError(404, "skill.not_found_in_source", {"source": source})
                if repo.status_code != 200:
                    raise MarketplaceError(
                        503, "skill.marketplace_unavailable", {"status_code": repo.status_code}
                    )
                branch = repo.json().get("default_branch") or "HEAD"
                tree = await client.get(
                    f"{GITHUB_API_BASE}/repos/{source}/git/trees/{branch}",
                    params={"recursive": "true"},
                )
        except httpx.HTTPError as exc:
            logger.info("github tree lookup failed for %s: %s", source, exc)
            raise MarketplaceError(503, "skill.marketplace_unavailable", {}) from exc
        if tree.status_code == 403:  # GitHub API rate limit
            self._rate_limited_until = time.monotonic() + 60
            raise MarketplaceError(429, "skill.marketplace_rate_limited", {"retry_after_s": 60})
        if tree.status_code != 200:
            raise MarketplaceError(
                503, "skill.marketplace_unavailable", {"status_code": tree.status_code}
            )
        paths = [
            item["path"]
            for item in tree.json().get("tree", [])
            if item.get("type") == "blob" and isinstance(item.get("path"), str)
        ]
        self._tree_cache.put(cache_key, paths)
        return paths

    # -- HTTP helpers --------------------------------------------------------------

    async def _probe_text(self, url: str) -> str | None:
        """Fetch ``url``; ``None`` on 404, a keyed error on anything else."""
        try:
            async with httpx.AsyncClient(
                timeout=CONTENT_TIMEOUT_S, follow_redirects=True
            ) as client:
                response = await client.get(url)
        except httpx.HTTPError as exc:
            logger.info("fetch failed %s: %s", url, exc)
            raise MarketplaceError(503, "skill.marketplace_unavailable", {}) from exc
        if response.status_code == 404:
            return None
        return self._decode(response)

    async def _fetch_text(self, url: str) -> str:
        """Fetch ``url``; a 404 is a structured not-found, not ``None``."""
        try:
            async with httpx.AsyncClient(
                timeout=CONTENT_TIMEOUT_S, follow_redirects=True
            ) as client:
                response = await client.get(url)
        except httpx.HTTPError as exc:
            logger.info("fetch failed %s: %s", url, exc)
            raise MarketplaceError(503, "skill.marketplace_unavailable", {}) from exc
        if response.status_code == 404:
            raise MarketplaceError(404, "skill.not_found_in_source", {"url": url})
        return self._decode(response)

    def _decode(self, response: httpx.Response) -> str:
        if response.status_code == 403:
            self._rate_limited_until = time.monotonic() + 60
            raise MarketplaceError(429, "skill.marketplace_rate_limited", {"retry_after_s": 60})
        if response.status_code != 200:
            raise MarketplaceError(
                503, "skill.marketplace_unavailable", {"status_code": response.status_code}
            )
        text = response.text
        if len(text.encode("utf-8")) > MAX_SKILL_FILE_BYTES:
            raise MarketplaceError(422, "skill.too_large", {"max_bytes": MAX_SKILL_FILE_BYTES})
        return text

    def _raise_if_rate_limited(self) -> None:
        if time.monotonic() < self._rate_limited_until:
            raise MarketplaceError(429, "skill.marketplace_rate_limited", {"retry_after_s": 60})

    def _to_content(self, source: str, skill_id: str, path: str, text: str) -> SkillContent:
        frontmatter, body = _parse_frontmatter(text)
        body = body.strip() or text.strip()
        license_value = frontmatter.get("license")
        return SkillContent(
            skill_id=skill_id,
            source=source,
            name=str(frontmatter.get("name") or skill_id)[:200],
            description=str(frontmatter.get("description") or "")[:2_000],
            body=body,
            content_sha256=hashlib.sha256(body.encode("utf-8")).hexdigest(),
            license=str(license_value)[:200] if license_value else None,
            path=path,
            source_url=f"https://github.com/{source}/tree/HEAD/{path.rsplit('/', 1)[0]}",
        )
