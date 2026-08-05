"""Kiro CLI adapter regression tests."""

from __future__ import annotations

import json
import subprocess

import pytest

from revai.domain.enums import ProviderId
from revai.domain.models import Credentials, RevaiConfig
from revai.providers.base import AnalysisRequest
from revai.providers.detection import CLI_SPECS, resolve_executable, run_command
from revai.providers.registry import build_registry


async def test_kiro_cli_adapter_runs_non_interactive_chat(monkeypatch) -> None:
    provider = build_registry(RevaiConfig(), Credentials()).get(ProviderId.KIRO_CLI)

    assert provider is not None

    captured: dict[str, object] = {}

    def fake_run(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(args, 0, b'{"findings":[]}', b"")

    monkeypatch.setattr(
        "revai.providers.cli.kiro.resolve_executable",
        lambda _: ("kiro-cli", r"C:\\kiro-cli.exe"),
    )
    monkeypatch.setattr("revai.providers.cli.kiro.subprocess.run", fake_run)

    events = [
        event
        async for event in provider.analyze(
            AnalysisRequest(
                model="claude-haiku-4.5",
                system_prompt="Return only JSON.",
                user_prompt="Review app.py.",
                json_schema={"type": "object"},
                timeout_s=30,
            )
        )
    ]

    assert captured["args"][:5] == [
        r"C:\\kiro-cli.exe",
        "chat",
        "--no-interactive",
        "--model",
        "claude-haiku-4.5",
    ]
    assert "Return only JSON." in captured["args"][-1]
    assert "Review app.py." in captured["args"][-1]
    assert events[0].type == "started"
    assert events[-1].type == "finished"
    assert events[-1].text == '{"findings":[]}'


@pytest.mark.cli
async def test_installed_kiro_cli_advertises_haiku() -> None:
    """Verify the vendor CLI contract without spending model credits by default."""

    spec = next(spec for spec in CLI_SPECS if spec.provider_id is ProviderId.KIRO_CLI)
    resolved = resolve_executable(spec)
    if resolved is None:
        pytest.skip("Kiro CLI is not installed.")

    _, executable = resolved
    result = await run_command(executable, ["chat", "--list-models", "--format", "json"])

    assert result.ok, result.combined
    payload = json.loads(result.stdout)
    model_ids = {model["model_id"] for model in payload["models"]}
    assert "claude-haiku-4.5" in model_ids
