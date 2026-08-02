"""Phase 4 deterministic pipeline contracts."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from revai.analyzers.eslint import parse_eslint_output
from revai.analyzers.gitleaks import parse_gitleaks_output
from revai.analyzers.ruff import parse_ruff_output
from revai.analyzers.runner import _process
from revai.analyzers.semgrep import parse_semgrep_output
from revai.domain.enums import FindingSource
from revai.git.repo import DiffFile
from revai.pipeline.deterministic import (
    ParsedHunk,
    build_chunks,
    filter_changed_files,
    parse_unified_diff,
)

PATCH = """\
diff --git a/src/calculator.py b/src/calculator.py
index 1111111..2222222 100644
--- a/src/calculator.py
+++ b/src/calculator.py
@@ -1,2 +1,3 @@
 def calculate():
+    unused = 42
     return 1
"""


def test_filter_drops_generated_lock_binary_and_vendored_files() -> None:
    files = [
        DiffFile(path="src/app.py", additions=2, deletions=0),
        DiffFile(path="package-lock.json", additions=10, deletions=2),
        DiffFile(path="vendor/library.js", additions=3, deletions=1),
        DiffFile(path="dist/app.min.js", additions=1, deletions=1),
        DiffFile(path="assets/logo.png", additions=0, deletions=0, binary=True),
    ]

    kept, skipped = filter_changed_files(files)

    assert [item.path for item in kept] == ["src/app.py"]
    assert [item.path for item in skipped] == [
        "package-lock.json",
        "vendor/library.js",
        "dist/app.min.js",
        "assets/logo.png",
    ]


def test_parse_keeps_added_and_removed_line_numbers() -> None:
    hunks = parse_unified_diff(PATCH, allowed_paths={"src/calculator.py"})

    assert len(hunks) == 1
    assert hunks[0].path == "src/calculator.py"
    assert hunks[0].added_lines == {2}
    assert hunks[0].removed_lines == set()
    assert hunks[0].changed_text == "    unused = 42"


def test_chunker_uses_python_symbol_boundaries_and_honours_budget(
    tmp_path: Path,
) -> None:
    source = tmp_path / "src" / "calculator.py"
    source.parent.mkdir()
    source.write_text(
        "def calculate():\n"
        "    unused = 42\n"
        "    return 1\n",
        encoding="utf-8",
    )
    hunks = parse_unified_diff(PATCH, allowed_paths={"src/calculator.py"})

    chunks = build_chunks(tmp_path, hunks, max_tokens=20)

    assert len(chunks) == 1
    assert chunks[0].path == "src/calculator.py"
    assert chunks[0].symbol == "calculate"
    assert chunks[0].line_start == 1
    assert chunks[0].line_end == 3
    assert chunks[0].estimated_tokens <= 20


def test_chunker_covers_each_changed_symbol_in_one_hunk(tmp_path: Path) -> None:
    source = tmp_path / "app.py"
    source.write_text(
        "import os\n\ndef auth(token):\n    return eval(token)\n",
        encoding="utf-8",
    )
    patch = """\
diff --git a/app.py b/app.py
index 1111111..2222222 100644
--- a/app.py
+++ b/app.py
@@ -1 +1,4 @@
-answer = 42
+import os
+
+def auth(token):
+    return eval(token)
"""
    hunks = parse_unified_diff(patch, allowed_paths={"app.py"})

    chunks = build_chunks(tmp_path, hunks, max_tokens=100)

    assert [(chunk.symbol, chunk.line_start, chunk.line_end) for chunk in chunks] == [
        (None, 1, 1),
        ("auth", 3, 4),
    ]


def test_chunker_uses_tree_sitter_boundaries_for_typescript(tmp_path: Path) -> None:
    source = tmp_path / "src" / "calculator.ts"
    source.parent.mkdir()
    source.write_text(
        "function calculate() {\n"
        "  const unused = 42;\n"
        "  return 1;\n"
        "}\n",
        encoding="utf-8",
    )
    patch = PATCH.replace("calculator.py", "calculator.ts").replace(
        "def calculate():\n+    unused = 42\n     return 1",
        "function calculate() {\n+  const unused = 42;\n   return 1;",
    )
    hunks = parse_unified_diff(patch, allowed_paths={"src/calculator.ts"})

    chunks = build_chunks(tmp_path, hunks, max_tokens=40)

    assert len(chunks) == 1
    assert chunks[0].symbol == "calculate"
    assert chunks[0].line_start == 1
    assert chunks[0].line_end == 4


def test_chunker_keeps_native_parsers_alive_across_mixed_languages(tmp_path: Path) -> None:
    typescript = tmp_path / "src" / "service.ts"
    python = tmp_path / "src" / "service.py"
    typescript.parent.mkdir()
    typescript.write_text(
        "export function greet(name: string) {\n  return `Hello ${name}`;\n}\n",
        encoding="utf-8",
    )
    python.write_text("def greet(name):\n    return f'Hello {name}'\n", encoding="utf-8")
    hunks = [
        ParsedHunk(
            path="src/service.ts",
            source_start=1,
            target_start=1,
            added_lines={2},
            removed_lines=set(),
            changed_text="+  return `Hello ${name}`;",
        ),
        ParsedHunk(
            path="src/service.py",
            source_start=1,
            target_start=1,
            added_lines={2},
            removed_lines=set(),
            changed_text="+    return f'Hello {name}'",
        ),
    ]

    chunks = build_chunks(tmp_path, hunks, max_tokens=100)

    assert [chunk.symbol for chunk in chunks] == ["greet", "greet"]


def test_ruff_json_is_normalized_into_a_finding(tmp_path: Path) -> None:
    source = tmp_path / "src" / "app.py"
    source.parent.mkdir()
    source.write_text("import os\n", encoding="utf-8")
    payload = json.dumps(
        [
            {
                "code": "F401",
                "message": "`os` imported but unused",
                "filename": str(source),
                "location": {"row": 1, "column": 1},
                "end_location": {"row": 1, "column": 10},
                "fix": None,
                "noqa_row": 1,
                "url": "https://docs.astral.sh/ruff/rules/unused-import/",
            }
        ]
    )

    findings = parse_ruff_output(payload, tmp_path)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.source is FindingSource.RUFF
    assert finding.rule_id == "F401"
    assert finding.file == "src/app.py"
    assert finding.line_start == 1
    assert finding.title == "F401: `os` imported but unused"


def test_eslint_json_is_normalized_into_a_finding(tmp_path: Path) -> None:
    source = tmp_path / "src" / "app.ts"
    source.parent.mkdir()
    source.write_text("const unused = 1;\n", encoding="utf-8")
    payload = json.dumps(
        [
            {
                "filePath": str(source),
                "messages": [
                    {
                        "ruleId": "@typescript-eslint/no-unused-vars",
                        "severity": 2,
                        "message": "'unused' is assigned a value but never used.",
                        "line": 1,
                        "endLine": 1,
                    }
                ],
            }
        ]
    )

    findings = parse_eslint_output(payload, tmp_path)

    assert len(findings) == 1
    assert findings[0].source is FindingSource.ESLINT
    assert findings[0].rule_id == "@typescript-eslint/no-unused-vars"
    assert findings[0].file == "src/app.ts"


def test_semgrep_json_is_normalized_into_a_security_finding(tmp_path: Path) -> None:
    payload = json.dumps(
        {
            "results": [
                {
                    "check_id": "python.lang.security.audit.eval-detected",
                    "path": "src/app.py",
                    "start": {"line": 4, "col": 1},
                    "end": {"line": 4, "col": 20},
                    "extra": {
                        "message": "Use of eval detected",
                        "severity": "ERROR",
                        "metadata": {"category": "security"},
                    },
                }
            ]
        }
    )

    findings = parse_semgrep_output(payload, tmp_path)

    assert len(findings) == 1
    assert findings[0].source is FindingSource.SEMGREP
    assert findings[0].category.value == "security"
    assert findings[0].severity.value == "critical"


def test_gitleaks_output_never_persists_the_detected_secret(tmp_path: Path) -> None:
    payload = json.dumps(
        [
            {
                "Description": "Generic API Key",
                "StartLine": 7,
                "EndLine": 7,
                "File": "src/settings.py",
                "RuleID": "generic-api-key",
                "Secret": "do-not-persist-this-value",
                "Match": "api_key=do-not-persist-this-value",
            }
        ]
    )

    findings = parse_gitleaks_output(payload, tmp_path)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.source is FindingSource.GITLEAKS
    assert finding.category.value == "security"
    assert "do-not-persist-this-value" not in finding.model_dump_json()


def test_analyzer_process_works_on_a_selector_event_loop(tmp_path: Path) -> None:
    """Uvicorn reload uses this loop on Windows, where async subprocesses fail."""
    loop = asyncio.SelectorEventLoop()
    try:
        returncode, stdout, stderr = loop.run_until_complete(
            _process(
                [sys.executable, "-c", "print('selector analyzer ok')"],
                tmp_path,
            )
        )
    finally:
        loop.close()

    assert returncode == 0, stderr
    assert "selector analyzer ok" in stdout
