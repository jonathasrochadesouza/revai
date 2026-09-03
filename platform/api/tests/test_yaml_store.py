"""Storage layer tests.

The property-based ones matter most: they assert the guarantees that make YAML a
defensible choice over a database — round-trip fidelity and atomicity.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given
from hypothesis import settings as hyp_settings
from hypothesis import strategies as st
from pydantic import BaseModel

from revai.domain.enums import (
    Category,
    EngineMode,
    FindingSource,
    ProviderId,
    Severity,
)
from revai.domain.models import (
    BudgetConfig,
    Credentials,
    EngineConfig,
    Finding,
    ProviderCredential,
    RevaiConfig,
)
from revai.storage.base import StorageError
from revai.storage.yaml_store import YamlStore, atomic_write

# ---------------------------------------------------------------------------
# atomic_write
# ---------------------------------------------------------------------------


def test_atomic_write_creates_missing_parents(tmp_path: Path) -> None:
    target = tmp_path / "deep" / "nested" / "file.yaml"

    atomic_write(target, "key: value\n")

    assert target.read_text(encoding="utf-8") == "key: value\n"


def test_atomic_write_replaces_existing_content(tmp_path: Path) -> None:
    target = tmp_path / "file.yaml"
    atomic_write(target, "first: 1\n")

    atomic_write(target, "second: 2\n")

    assert target.read_text(encoding="utf-8") == "second: 2\n"


def test_atomic_write_leaves_no_temporary_files(tmp_path: Path) -> None:
    """A leaked temp file would eventually be picked up by a directory glob."""
    target = tmp_path / "file.yaml"

    atomic_write(target, "key: value\n")

    assert [p.name for p in tmp_path.iterdir()] == ["file.yaml"]


def test_atomic_write_always_uses_utf8_without_bom(tmp_path: Path) -> None:
    """The PowerShell version emitted UTF-16LE via `>`; this must not regress."""
    target = tmp_path / "accents.yaml"

    atomic_write(target, "name: Jonathas Souza — ação\n")

    raw = target.read_bytes()
    assert not raw.startswith(b"\xff\xfe")  # UTF-16LE BOM
    assert not raw.startswith(b"\xef\xbb\xbf")  # UTF-8 BOM
    assert "ação" in raw.decode("utf-8")


def test_atomic_write_normalises_newlines(tmp_path: Path) -> None:
    """`newline="\\n"` must survive on Windows, where the default would be CRLF."""
    target = tmp_path / "file.yaml"

    atomic_write(target, "a: 1\nb: 2\n")

    assert b"\r\n" not in target.read_bytes()


def test_atomic_write_reports_a_useful_error(tmp_path: Path) -> None:
    """Writing over a directory must raise StorageError, not a bare OSError."""
    blocked = tmp_path / "blocked"
    blocked.mkdir()

    with pytest.raises(StorageError, match=r"storage\.write_failed"):
        atomic_write(blocked, "x: 1\n")


# ---------------------------------------------------------------------------
# YamlStore — reading
# ---------------------------------------------------------------------------


def test_read_returns_none_when_file_is_absent(tmp_path: Path) -> None:
    """A fresh install has no config; that is a normal state, not an error."""
    store: YamlStore[RevaiConfig] = YamlStore(RevaiConfig)

    assert store.read(tmp_path / "nothing.yaml") is None


def test_read_returns_none_for_an_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "empty.yaml"
    path.write_text("", encoding="utf-8")
    store: YamlStore[RevaiConfig] = YamlStore(RevaiConfig)

    assert store.read(path) is None


def test_read_rejects_malformed_yaml_naming_the_file(tmp_path: Path) -> None:
    path = tmp_path / "broken.yaml"
    path.write_text("engine: [unclosed\n", encoding="utf-8")
    store: YamlStore[RevaiConfig] = YamlStore(RevaiConfig)

    with pytest.raises(StorageError, match=r"storage\.invalid_yaml") as excinfo:
        store.read(path)
    assert excinfo.value.params["filename"] == "broken.yaml"


def test_read_rejects_a_non_mapping_document(tmp_path: Path) -> None:
    path = tmp_path / "list.yaml"
    path.write_text("- one\n- two\n", encoding="utf-8")
    store: YamlStore[RevaiConfig] = YamlStore(RevaiConfig)

    with pytest.raises(StorageError, match=r"storage\.not_a_mapping"):
        store.read(path)


def test_read_reports_which_field_failed_validation(tmp_path: Path) -> None:
    """These files are hand-edited, so the error has to be actionable."""
    path = tmp_path / "config.yaml"
    path.write_text("budget:\n  max_spend_usd: -5\n", encoding="utf-8")
    store: YamlStore[RevaiConfig] = YamlStore(RevaiConfig)

    with pytest.raises(StorageError, match=r"storage\.schema_mismatch") as excinfo:
        store.read(path)
    assert "max_spend_usd" in excinfo.value.params["detail"]


def test_read_rejects_unknown_fields(tmp_path: Path) -> None:
    """`extra="forbid"` turns a typo into an error instead of a silent no-op."""
    path = tmp_path / "config.yaml"
    path.write_text("engien: {}\n", encoding="utf-8")
    store: YamlStore[RevaiConfig] = YamlStore(RevaiConfig)

    with pytest.raises(StorageError):
        store.read(path)


# ---------------------------------------------------------------------------
# YamlStore — round-trip
# ---------------------------------------------------------------------------


def test_round_trip_preserves_the_document(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    store: YamlStore[RevaiConfig] = YamlStore(RevaiConfig)
    original = RevaiConfig(
        engine=EngineConfig(
            mode=EngineMode.CLI,
            provider_id=ProviderId.COPILOT_CLI,
            model="gpt-5-codex",
        ),
        budget=BudgetConfig(max_spend_usd=2.5, warn_above_usd=1.0),
    )

    store.write(path, original)
    restored = store.read(path)

    assert restored is not None
    assert restored.engine.mode is EngineMode.CLI
    assert restored.engine.provider_id is ProviderId.COPILOT_CLI
    assert restored.budget.max_spend_usd == 2.5


def test_enums_serialise_as_plain_scalars(tmp_path: Path) -> None:
    """Tagged Python objects in the file would break `Save to config.yaml`'s promise
    that the result is readable YAML."""
    path = tmp_path / "config.yaml"
    store: YamlStore[RevaiConfig] = YamlStore(RevaiConfig)

    store.write(path, RevaiConfig())
    raw = path.read_text(encoding="utf-8")

    assert "!!python" not in raw
    assert "mode: api" in raw


def test_datetimes_serialise_as_iso_strings(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    store: YamlStore[RevaiConfig] = YamlStore(RevaiConfig)

    store.write(path, RevaiConfig())
    restored = store.read(path)

    assert restored is not None
    assert restored.updated_at.tzinfo is not None  # timezone survived


def test_credentials_round_trip_with_a_dict_key(tmp_path: Path) -> None:
    """Enum-keyed dicts are the one shape most likely to break serialisation."""
    path = tmp_path / "credentials.yaml"
    store: YamlStore[Credentials] = YamlStore(Credentials)
    document = Credentials()
    document.put(
        ProviderCredential(
            provider_id=ProviderId.OPENROUTER, api_key="sk-or-v1-secret", label="main"
        )
    )

    store.write(path, document)
    restored = store.read(path)

    assert restored is not None
    credential = restored.get(ProviderId.OPENROUTER)
    assert credential is not None
    assert credential.api_key == "sk-or-v1-secret"


def test_write_is_repeatable(tmp_path: Path) -> None:
    """Saving twice must not append or duplicate keys."""
    path = tmp_path / "config.yaml"
    store: YamlStore[RevaiConfig] = YamlStore(RevaiConfig)
    document = RevaiConfig()

    store.write(path, document)
    first = path.read_text(encoding="utf-8")
    store.write(path, document)
    second = path.read_text(encoding="utf-8")

    assert first.count("engine:") == 1
    assert second.count("engine:") == 1


def test_lock_sidecar_does_not_collide_with_the_document(tmp_path: Path) -> None:
    """The lock lives beside the file, so a `*.yaml` glob must not pick it up."""
    path = tmp_path / "config.yaml"
    store: YamlStore[RevaiConfig] = YamlStore(RevaiConfig)

    store.write(path, RevaiConfig())

    assert [p.name for p in tmp_path.glob("*.yaml")] == ["config.yaml"]


# ---------------------------------------------------------------------------
# Property: round-trip fidelity
# ---------------------------------------------------------------------------


class _Sample(BaseModel):
    """A deliberately awkward model: unicode, floats, nesting, empty containers."""

    name: str
    count: int
    ratio: float
    flag: bool
    tags: list[str]
    nested: dict[str, int]


_TEXT = st.text(alphabet=st.characters(blacklist_categories=("Cs", "Cc")), min_size=0, max_size=60)


@hyp_settings(
    max_examples=120,
    # These properties touch the filesystem. On Windows the first write to a fresh
    # temp directory can take several hundred milliseconds while the OS warms up,
    # which trips any fixed deadline and reports as flakiness rather than a real
    # failure. Timing is not what we are asserting here.
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    name=_TEXT,
    count=st.integers(min_value=-1_000_000, max_value=1_000_000),
    ratio=st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
    flag=st.booleans(),
    tags=st.lists(_TEXT, max_size=6),
    nested=st.dictionaries(
        st.text(alphabet="abcdefghijklmnop", min_size=1, max_size=8),
        st.integers(min_value=-1000, max_value=1000),
        max_size=6,
    ),
)
def test_property_any_document_survives_a_round_trip(
    tmp_path_factory: pytest.TempPathFactory,
    name: str,
    count: int,
    ratio: float,
    flag: bool,
    tags: list[str],
    nested: dict[str, int],
) -> None:
    """Whatever goes in comes back out identical.

    This is the guarantee that makes plain YAML acceptable as the datastore.
    """
    path = tmp_path_factory.mktemp("prop") / "sample.yaml"
    store: YamlStore[_Sample] = YamlStore(_Sample)
    original = _Sample(name=name, count=count, ratio=ratio, flag=flag, tags=tags, nested=nested)

    store.write(path, original)
    restored = store.read(path)

    assert restored is not None
    assert restored.count == original.count
    assert restored.flag == original.flag
    assert restored.tags == original.tags
    assert restored.nested == original.nested
    assert restored.ratio == pytest.approx(original.ratio)


# ---------------------------------------------------------------------------
# Property: atomicity
# ---------------------------------------------------------------------------


@hyp_settings(
    max_examples=60,
    deadline=None,  # first-call disk warm-up on Windows blows any fixed deadline
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    payloads=st.lists(
        st.text(
            alphabet=st.characters(
                # Carriage returns are excluded because `read_text()` applies
                # *universal newlines* and decodes a "\r" on disk as "\n". A
                # payload of "\r" would fail an equality check even though the
                # bytes were written faithfully. Line endings are covered
                # byte-for-byte by the tests below.
                blacklist_characters="\r",
                # Surrogates are excluded because they are not encodable as UTF-8
                # at all, so the correct behaviour is an error rather than a
                # successful write. That path has its own test below.
                blacklist_categories=("Cs",),
            ),
            min_size=1,
            max_size=200,
        ),
        min_size=2,
        max_size=8,
    )
)
def test_property_a_file_is_never_partially_written(
    tmp_path_factory: pytest.TempPathFactory, payloads: list[str]
) -> None:
    """After every write the file equals exactly one complete payload.

    Never a prefix, never a blend of two. This is what `os.replace` buys us over
    opening the target and truncating it in place.
    """
    path = tmp_path_factory.mktemp("atomic") / "file.txt"

    for payload in payloads:
        atomic_write(path, payload)
        assert path.read_text(encoding="utf-8") == payload

    assert path.read_text(encoding="utf-8") == payloads[-1]


def test_line_endings_are_written_verbatim(tmp_path: Path) -> None:
    """`newline="\\n"` prevents translation, it does not rewrite the payload.

    On Windows the default would silently turn every "\\n" we write into "\\r\\n".
    Pinning it means the bytes on disk are exactly the bytes we passed in, so a
    file produced on Windows and one produced on Linux are identical — which is
    what keeps these YAML files diffable across a mixed team.

    Note this is the *write* side only. `read_text()` applies universal newlines
    and will decode "\\r" as "\\n", which is why the assertion here is on raw bytes.
    """
    path = tmp_path / "endings.txt"

    atomic_write(path, "a\r\nb\rc\n")

    assert path.read_bytes() == b"a\r\nb\rc\n"


def test_newlines_are_not_expanded_to_crlf(tmp_path: Path) -> None:
    """The regression that actually matters: no CRLF creeping in on Windows."""
    path = tmp_path / "unix.txt"

    atomic_write(path, "a\nb\nc\n")

    assert path.read_bytes() == b"a\nb\nc\n"


def test_unencodable_content_raises_storage_error(tmp_path: Path) -> None:
    """A lone surrogate must fail as a StorageError, not a bare UnicodeEncodeError.

    Found by Hypothesis, and reachable from the API in practice: Pydantic accepts a
    string containing U+D800 and ``json.dumps`` escapes it as ``\\ud800``, so a
    client can put one in a request body. Without translation the route would return
    500 instead of naming the offending character.
    """
    path = tmp_path / "surrogate.yaml"

    with pytest.raises(StorageError, match=r"storage\.write_unencodable_character"):
        atomic_write(path, "\ud800")


def test_a_failed_encode_leaves_no_partial_file(tmp_path: Path) -> None:
    """The atomicity guarantee has to hold for encoding failures too."""
    path = tmp_path / "target.yaml"
    atomic_write(path, "good: true\n")

    with pytest.raises(StorageError):
        atomic_write(path, "\ud800")

    # The previous content survives, and no temp file is left behind.
    assert path.read_text(encoding="utf-8") == "good: true\n"
    assert [p.name for p in tmp_path.iterdir()] == ["target.yaml"]


@hyp_settings(
    max_examples=40,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(count=st.integers(min_value=1, max_value=12))
def test_property_repeated_writes_leave_one_file(
    tmp_path_factory: pytest.TempPathFactory, count: int
) -> None:
    """No amount of writing may accumulate temporary files."""
    directory = tmp_path_factory.mktemp("clean")
    path = directory / "file.yaml"

    for index in range(count):
        atomic_write(path, f"iteration: {index}\n")

    assert [entry.name for entry in os.scandir(directory)] == ["file.yaml"]


# ---------------------------------------------------------------------------
# Property: findings
# ---------------------------------------------------------------------------


@hyp_settings(max_examples=100)
@given(
    start=st.integers(min_value=1, max_value=10_000),
    span=st.integers(min_value=0, max_value=500),
)
def test_property_finding_line_range_is_always_valid(start: int, span: int) -> None:
    finding = Finding(
        severity=Severity.MEDIUM,
        category=Category.MAINTAINABILITY,
        title="t",
        description="d",
        file="a.py",
        line_start=start,
        line_end=start + span,
        source=FindingSource.RUFF,
    )

    assert finding.line_end is not None
    assert finding.line_end >= finding.line_start


def test_finding_rejects_an_inverted_line_range() -> None:
    """Silently accepting this would corrupt the diff viewer."""
    with pytest.raises(ValueError, match="precedes line_start"):
        Finding(
            severity=Severity.LOW,
            category=Category.STYLE,
            title="t",
            description="d",
            file="a.py",
            line_start=100,
            line_end=50,
            source=FindingSource.ESLINT,
        )


def test_finding_ids_are_unique() -> None:
    def make() -> Finding:
        return Finding(
            severity=Severity.LOW,
            category=Category.STYLE,
            title="t",
            description="d",
            file="a.py",
            line_start=1,
            source=FindingSource.AI,
        )

    assert len({make().id for _ in range(500)}) == 500


def test_masked_key_never_reveals_the_middle() -> None:
    credential = ProviderCredential(
        provider_id=ProviderId.OPENROUTER,
        api_key="sk-or-v1-0123456789abcdefghijklmnop",
    )

    masked = credential.masked()

    assert "0123456789abcdef" not in masked
    assert masked.startswith("sk-or-v1")
    assert masked.endswith("mnop")
