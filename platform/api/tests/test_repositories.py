"""Repository behaviour, including the safety rails around filenames."""

from __future__ import annotations

import pytest

from revai.config import Settings
from revai.domain.enums import (
    Category,
    FindingSource,
    ProviderId,
    ReviewScope,
    ReviewStatus,
    Severity,
)
from revai.domain.models import (
    Credentials,
    EngineConfig,
    Finding,
    Project,
    ProviderCredential,
    RevaiConfig,
    Review,
)
from revai.storage.base import StorageError
from revai.storage.repositories import (
    ConfigRepository,
    CredentialsRepository,
    ProjectRepository,
    ReviewRepository,
)


def _project(name: str = "demo") -> Project:
    return Project(name=name, path=f"C:/repos/{name}", base_branch="develop")


def _review(project_id: str) -> Review:
    return Review(project_id=project_id, scope=ReviewScope.BRANCH_DIFF)


def _finding() -> Finding:
    return Finding(
        severity=Severity.CRITICAL,
        category=Category.SECURITY,
        title="Hardcoded secret",
        description="A signing key is embedded in the source.",
        file="src/Token.java",
        line_start=99,
        line_end=101,
        source=FindingSource.SEMGREP,
        rule_id="CWE-798",
        confidence=0.92,
    )


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def test_config_defaults_when_no_file_exists(settings: Settings) -> None:
    repo = ConfigRepository(settings)

    config = repo.load()

    assert repo.exists() is False
    assert config.engine.provider_id is ProviderId.OPENROUTER


def test_config_survives_a_save_and_reload(settings: Settings) -> None:
    """The phase-1 acceptance criterion: configuration outlives the process."""
    repo = ConfigRepository(settings)
    config = repo.load()
    config.engine = EngineConfig(model="anthropic/claude-opus-4.1")
    config.budget.max_spend_usd = 3.75
    repo.save(config)

    reloaded = ConfigRepository(settings).load()

    assert reloaded.engine.model == "anthropic/claude-opus-4.1"
    assert reloaded.budget.max_spend_usd == 3.75


def test_config_file_is_human_readable(settings: Settings) -> None:
    repo = ConfigRepository(settings)
    repo.save(RevaiConfig())

    raw = repo.path.read_text(encoding="utf-8")

    assert "engine:" in raw
    assert "budget:" in raw
    assert "!!python" not in raw


# ---------------------------------------------------------------------------
# Credentials
# ---------------------------------------------------------------------------


def test_credentials_round_trip(settings: Settings) -> None:
    repo = CredentialsRepository(settings)
    document = Credentials()
    document.put(ProviderCredential(provider_id=ProviderId.OPENROUTER, api_key="sk-or-v1-abc"))
    repo.save(document)

    reloaded = CredentialsRepository(settings).load()

    credential = reloaded.get(ProviderId.OPENROUTER)
    assert credential is not None
    assert credential.api_key == "sk-or-v1-abc"


def test_credentials_removal(settings: Settings) -> None:
    repo = CredentialsRepository(settings)
    document = Credentials()
    document.put(ProviderCredential(provider_id=ProviderId.OPENAI, api_key="sk-x"))
    repo.save(document)

    document = repo.load()
    assert document.remove(ProviderId.OPENAI) is True
    repo.save(document)

    assert repo.load().configured == []


def test_credentials_live_outside_any_project(settings: Settings) -> None:
    """The protection that actually prevents committing a secret."""
    repo = CredentialsRepository(settings)

    assert repo.path.parent == settings.data_dir
    assert "projects" not in repo.path.parts


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------


def test_project_crud(settings: Settings) -> None:
    repo = ProjectRepository(settings)
    project = repo.save(_project())

    assert repo.get(project.id) is not None
    assert repo.exists(project.id) is True
    assert repo.delete(project.id) is True
    assert repo.get(project.id) is None


def test_project_list_is_newest_first(settings: Settings) -> None:
    repo = ProjectRepository(settings)
    for index in range(3):
        repo.save(_project(f"repo{index}"))

    listed = repo.list()

    assert len(listed) == 3
    assert listed == sorted(listed, key=lambda p: p.created_at, reverse=True)


def test_project_list_skips_an_unreadable_file(settings: Settings) -> None:
    """One corrupt file must not hide every other project."""
    repo = ProjectRepository(settings)
    repo.save(_project("good"))
    (settings.projects_dir / "corrupt.yaml").write_text("{{{", encoding="utf-8")

    listed = repo.list()

    assert [p.name for p in listed] == ["good"]


def test_deleting_a_project_removes_its_reviews(settings: Settings) -> None:
    """Otherwise orphaned reviews accumulate forever."""
    projects = ProjectRepository(settings)
    reviews = ReviewRepository(settings)
    project = projects.save(_project())
    review = reviews.save(_review(project.id))

    projects.delete(project.id)

    assert reviews.get(review.id, project.id) is None


def test_project_name_rejects_path_separators() -> None:
    with pytest.raises(ValueError, match="path separators"):
        Project(name="../escape", path="C:/x")


def test_project_base_branch_is_configurable() -> None:
    """Replaces the `develop` hardcoded in both PowerShell diff scripts."""
    assert _project().base_branch == "develop"
    assert Project(name="x", path="C:/x").base_branch == "main"


# ---------------------------------------------------------------------------
# Reviews
# ---------------------------------------------------------------------------


def test_review_round_trip_with_findings(settings: Settings) -> None:
    repo = ReviewRepository(settings)
    review = _review("proj1")
    review.findings.append(_finding())
    review.status = ReviewStatus.COMPLETED
    repo.save(review)

    reloaded = repo.get(review.id, "proj1")

    assert reloaded is not None
    assert reloaded.status is ReviewStatus.COMPLETED
    assert reloaded.findings[0].rule_id == "CWE-798"
    assert reloaded.findings[0].confidence == pytest.approx(0.92)


def test_reviews_are_partitioned_by_project(settings: Settings) -> None:
    repo = ReviewRepository(settings)
    repo.save(_review("alpha"))
    repo.save(_review("beta"))
    repo.save(_review("beta"))

    assert len(repo.list("beta")) == 2
    assert len(repo.list("alpha")) == 1
    assert len(repo.list()) == 3


def test_review_can_be_found_without_its_project_id(settings: Settings) -> None:
    repo = ReviewRepository(settings)
    review = repo.save(_review("gamma"))

    assert repo.get(review.id) is not None


def test_review_counts_only_open_findings(settings: Settings) -> None:
    review = _review("p")
    review.findings.append(_finding())
    dismissed = _finding()
    dismissed.status = "dismissed"  # type: ignore[assignment]
    review.findings.append(dismissed)

    assert review.count(Severity.CRITICAL) == 1


def test_review_sorts_critical_first() -> None:
    review = _review("p")
    low = _finding()
    low.severity = Severity.LOW
    review.findings.extend([low, _finding()])

    assert review.sorted_findings[0].severity is Severity.CRITICAL


# ---------------------------------------------------------------------------
# Path traversal
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "identifier",
    ["../escape", "..\\escape", "a/b", "a\\b", "", "with space", "semi;colon"],
)
def test_identifiers_that_could_escape_the_data_dir_are_rejected(
    settings: Settings, identifier: str
) -> None:
    """Ids arrive from URL path parameters, so this is the last line of defence."""
    repo = ProjectRepository(settings)

    with pytest.raises(StorageError):
        repo.get(identifier)


def test_generated_ids_are_filename_safe(settings: Settings) -> None:
    repo = ProjectRepository(settings)

    for _ in range(50):
        saved = repo.save(_project())
        assert repo.get(saved.id) is not None
