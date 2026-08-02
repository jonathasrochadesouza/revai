"""Phase 7 export, archive, and insights flows."""

from __future__ import annotations

import io
import json
import zipfile
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from revai.config import Settings
from revai.domain.enums import (
    Category,
    FindingSource,
    FindingStatus,
    ReviewScope,
    ReviewStatus,
    Severity,
)
from revai.domain.models import Finding, Project, Review, ReviewStats
from revai.export import legacy_findings_to_domain
from revai.storage.repositories import (
    CredentialsRepository,
    ProjectRepository,
    ReviewRepository,
)


def _seed(settings: Settings) -> tuple[Project, Review]:
    project = Project(
        id="project-1",
        name="Payments <img src=x onerror=alert(1)>",
        path="/tmp/payments",
        languages=["python"],
    )
    finding = Finding(
        id="finding-1",
        severity=Severity.CRITICAL,
        category=Category.SECURITY,
        title="Unescaped <script>alert(2)</script>",
        description="User data reaches an HTML response.",
        rationale="This can execute attacker-controlled markup.",
        file="src/report.py",
        line_start=10,
        line_end=12,
        source=FindingSource.SEMGREP,
        rule_id="CWE-79",
        confidence=0.98,
        suggested_patch="--- a/src/report.py\n+++ b/src/report.py\n@@ -10 +10 @@\n-unsafe\n+safe",
    )
    review = Review(
        id="review-1",
        project_id=project.id,
        scope=ReviewScope.BRANCH_DIFF,
        status=ReviewStatus.COMPLETED,
        base_branch="main",
        head_branch="feature/export",
        findings=[finding],
        stats=ReviewStats(cost_usd=0.0123, duration_ms=2_500),
        created_at=datetime.now(UTC) - timedelta(days=1),
        finished_at=datetime.now(UTC),
    )
    ProjectRepository(settings).save(project)
    ReviewRepository(settings).save(review)
    return project, review


def test_modern_json_export_contains_review_and_project(
    client: TestClient,
    settings: Settings,
) -> None:
    project, review = _seed(settings)

    response = client.get(f"/api/reviews/{review.id}/export?format=json")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.headers["content-disposition"].endswith('.json"')
    payload = response.json()
    assert payload["format_version"] == 1
    assert payload["project"]["id"] == project.id
    assert payload["review"]["findings"][0]["rule_id"] == "CWE-79"


def test_legacy_json_round_trips_supported_fields(
    client: TestClient,
    settings: Settings,
) -> None:
    _, review = _seed(settings)

    response = client.get(f"/api/reviews/{review.id}/export?format=json&legacy=true")

    assert response.status_code == 200
    payload = response.json()
    assert payload == [
        {
            "title": "Unescaped <script>alert(2)</script>",
            "priority": "Critical",
            "description": "User data reaches an HTML response.",
            "copilotSummary": "This can execute attacker-controlled markup.",
            "file": "src/report.py",
            "lines": "10-12",
        }
    ]
    imported = legacy_findings_to_domain(payload)
    assert imported[0].title == review.findings[0].title
    assert imported[0].severity is Severity.CRITICAL
    assert imported[0].line_start == 10
    assert imported[0].line_end == 12


def test_markdown_and_standalone_html_exports_are_safe(
    client: TestClient,
    settings: Settings,
) -> None:
    _, review = _seed(settings)

    markdown = client.get(f"/api/reviews/{review.id}/export?format=md")
    html = client.get(f"/api/reviews/{review.id}/export?format=html")

    assert markdown.status_code == 200
    assert "# RevAI review" in markdown.text
    assert "```diff" in markdown.text
    assert html.status_code == 200
    assert "<!doctype html>" in html.text
    assert "&lt;img src=x onerror=alert(1)&gt;" in html.text
    assert "&lt;script&gt;alert(2)&lt;/script&gt;" in html.text
    assert "<script>alert" not in html.text
    assert "http://" not in html.text
    assert "https://" not in html.text


def test_invalid_export_combinations_and_unknown_reviews_return_errors(
    client: TestClient,
    settings: Settings,
) -> None:
    _, review = _seed(settings)

    legacy_markdown = client.get(f"/api/reviews/{review.id}/export?format=md&legacy=true")
    missing = client.get("/api/reviews/not-found/export")
    traversal = client.get("/api/reviews/%2E%2E/export")

    assert legacy_markdown.status_code == 422
    assert missing.status_code == 404
    assert traversal.status_code in {404, 422}


def test_insights_aggregate_metrics_and_latest_project_health(
    client: TestClient,
    settings: Settings,
) -> None:
    project, review = _seed(settings)
    older = review.model_copy(deep=True)
    older.id = "review-older"
    older.created_at = datetime.now(UTC) - timedelta(days=3)
    older.findings[0].status = FindingStatus.FIXED
    older.stats.cost_usd = 0.005
    ReviewRepository(settings).save(older)

    response = client.get("/api/insights?range=30d")

    assert response.status_code == 200
    payload = response.json()
    assert payload["totals"] == {
        "reviews": 2,
        "completed_reviews": 2,
        "findings": 2,
        "open_findings": 1,
        "open_critical": 1,
        "resolved_findings": 1,
        "false_positives": 0,
        "total_cost_usd": 0.0173,
        "median_duration_ms": 2500,
    }
    assert payload["categories"]["security"] == 2
    assert payload["statuses"]["fixed"] == 1
    assert payload["projects"][0]["project_id"] == project.id
    assert payload["projects"][0]["health_score"] == 85
    assert payload["projects"][0]["health_change"] == -15
    assert [point["review_id"] for point in payload["trend"]] == [
        "review-older",
        "review-1",
    ]


def test_data_summary_and_full_archive_exclude_credentials(
    client: TestClient,
    settings: Settings,
) -> None:
    project, review = _seed(settings)
    credentials = CredentialsRepository(settings).load()
    # An on-disk credential file proves the archive excludes it by policy, not by absence.
    credentials.providers = {}
    CredentialsRepository(settings).save(credentials)
    settings.rules_dir.joinpath("custom.yaml").write_text("rules: []\n", encoding="utf-8")

    summary = client.get("/api/data")
    archive_response = client.post("/api/export/all")

    assert summary.status_code == 200
    assert summary.json()["projects"] == 1
    assert summary.json()["reviews"] == 1
    assert summary.json()["storage_bytes"] > 0
    assert summary.json()["credentials_included_in_archive"] is False
    assert archive_response.status_code == 200
    assert archive_response.headers["content-type"] == "application/zip"

    with zipfile.ZipFile(io.BytesIO(archive_response.content)) as archive:
        names = set(archive.namelist())
        assert "manifest.json" in names
        assert "config.json" in names
        assert f"projects/{project.id}.json" in names
        assert f"reviews/{project.id}/{review.id}.json" in names
        assert "rules/custom.yaml" in names
        assert all("credential" not in name for name in names)
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["credentials_included"] is False
