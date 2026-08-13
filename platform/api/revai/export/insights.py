"""Aggregate persisted reviews into dashboard-ready metrics."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta
from statistics import median
from typing import Literal

from pydantic import BaseModel, ConfigDict

from revai.domain.enums import Category, FindingStatus, ReviewStatus, Severity
from revai.domain.models import Project, Review

InsightRange = Literal["7d", "30d", "90d", "all"]


class _ResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InsightTotals(_ResponseModel):
    reviews: int
    completed_reviews: int
    findings: int
    open_findings: int
    open_critical: int
    resolved_findings: int
    false_positives: int
    total_cost_usd: float
    median_duration_ms: int


class ReviewTrendPoint(_ResponseModel):
    review_id: str
    project_id: str
    project_name: str
    created_at: datetime
    critical: int
    medium: int
    low: int


class ProjectInsight(_ResponseModel):
    project_id: str
    name: str
    languages: list[str]
    reviews: int
    open_critical: int
    open_findings: int
    health_score: int
    health_change: int | None
    last_reviewed_at: datetime | None


class InsightsResponse(_ResponseModel):
    range: InsightRange
    generated_at: datetime
    totals: InsightTotals
    categories: dict[str, int]
    statuses: dict[str, int]
    trend: list[ReviewTrendPoint]
    projects: list[ProjectInsight]


def build_insights(
    reviews: list[Review],
    projects: list[Project],
    selected_range: InsightRange,
    *,
    now: datetime | None = None,
) -> InsightsResponse:
    """Build deterministic metrics from YAML-backed domain objects.

    Totals and trend points respect the selected time range. A repository's health
    score uses its latest review within that same range so old findings are not
    repeatedly counted as current debt.
    """
    generated_at = now or datetime.now(UTC)
    scoped = _within_range(reviews, selected_range, generated_at)
    findings = [finding for review in scoped for finding in review.findings]
    open_findings = [finding for finding in findings if finding.status is FindingStatus.OPEN]

    durations = [review.stats.duration_ms for review in scoped if review.stats.duration_ms > 0]
    totals = InsightTotals(
        reviews=len(scoped),
        completed_reviews=sum(
            review.status in {ReviewStatus.COMPLETED, ReviewStatus.DEGRADED}
            for review in scoped
        ),
        findings=len(findings),
        open_findings=len(open_findings),
        open_critical=sum(finding.severity is Severity.CRITICAL for finding in open_findings),
        resolved_findings=sum(finding.status is FindingStatus.FIXED for finding in findings),
        false_positives=sum(finding.status is FindingStatus.FALSE_POSITIVE for finding in findings),
        total_cost_usd=round(sum(review.stats.cost_usd for review in scoped), 6),
        median_duration_ms=round(median(durations)) if durations else 0,
    )

    project_by_id = {project.id: project for project in projects}
    categories = Counter(finding.category.value for finding in findings)
    statuses = Counter(finding.status.value for finding in findings)

    chronological = sorted(scoped, key=lambda review: review.created_at)
    trend = [
        ReviewTrendPoint(
            review_id=review.id,
            project_id=review.project_id,
            project_name=(
                project_by_id[review.project_id].name
                if review.project_id in project_by_id
                else "Unknown project"
            ),
            created_at=review.created_at,
            critical=_severity_count(review, Severity.CRITICAL),
            medium=_severity_count(review, Severity.MEDIUM),
            low=_severity_count(review, Severity.LOW),
        )
        for review in chronological[-12:]
    ]

    grouped: dict[str, list[Review]] = {}
    for review in sorted(scoped, key=lambda item: item.created_at, reverse=True):
        grouped.setdefault(review.project_id, []).append(review)

    project_rows = [_project_insight(project, grouped.get(project.id, [])) for project in projects]
    project_rows.sort(key=lambda row: (row.reviews == 0, row.health_score, row.name.lower()))

    return InsightsResponse(
        range=selected_range,
        generated_at=generated_at,
        totals=totals,
        categories={category.value: categories[category.value] for category in Category},
        statuses={status.value: statuses[status.value] for status in FindingStatus},
        trend=trend,
        projects=project_rows,
    )


def _within_range(
    reviews: list[Review],
    selected_range: InsightRange,
    now: datetime,
) -> list[Review]:
    days = {"7d": 7, "30d": 30, "90d": 90}.get(selected_range)
    if days is None:
        return list(reviews)
    cutoff = now - timedelta(days=days)
    return [review for review in reviews if review.created_at >= cutoff]


def _severity_count(review: Review, severity: Severity) -> int:
    return sum(
        finding.severity is severity and finding.status is FindingStatus.OPEN
        for finding in review.findings
    )


def _open_count(review: Review) -> int:
    return sum(finding.status is FindingStatus.OPEN for finding in review.findings)


def _health_score(review: Review | None) -> int:
    if review is None:
        return 100
    penalty = sum(
        {
            Severity.CRITICAL: 15,
            Severity.MEDIUM: 5,
            Severity.LOW: 1,
        }[finding.severity]
        for finding in review.findings
        if finding.status is FindingStatus.OPEN
    )
    return max(0, 100 - penalty)


def _project_insight(project: Project, reviews: list[Review]) -> ProjectInsight:
    latest = reviews[0] if reviews else None
    previous = reviews[1] if len(reviews) > 1 else None
    health = _health_score(latest)
    change = health - _health_score(previous) if previous is not None else None
    return ProjectInsight(
        project_id=project.id,
        name=project.name,
        languages=project.languages,
        reviews=len(reviews),
        open_critical=_severity_count(latest, Severity.CRITICAL) if latest else 0,
        open_findings=_open_count(latest) if latest else 0,
        health_score=health,
        health_change=change,
        last_reviewed_at=latest.created_at if latest else None,
    )
