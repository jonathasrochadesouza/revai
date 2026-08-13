"""Small, dependency-free security checks for changed source files.

These rules deliberately cover only dangerous APIs with a high signal-to-noise
ratio. They complement Semgrep and Gitleaks so a missing optional executable never
turns an obvious dynamic-execution change into a silent pass.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from revai.domain.enums import Category, FindingSource, Severity
from revai.domain.models import Finding

_JAVASCRIPT_CALLS = re.compile(r"\b(?P<name>eval|Function)\s*\(")
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b[\w$]*(?:api[_-]?key|access[_-]?token|auth[_-]?token|token|secret|password)[\w$]*"
    r"\s*(?:=|:)\s*['\"][^'\"\r\n]{8,}['\"]"
)
_JAVA_SQL_CONCAT = re.compile(
    r"\b(?:executeQuery|executeUpdate|prepareStatement|createQuery)\s*\([^;\n]*\+"
)
_JAVA_SQL_VARIABLE_CONCAT = re.compile(
    r"(?i)\b(?:String|var)\s+[\w$]*(?:sql|query)[\w$]*\s*=\s*"
    r"[^;\n]*(?:select|insert|update|delete)[^;\n]*\+"
)
_JAVA_COMMAND = re.compile(r"\b(?:Runtime\.getRuntime\(\)\.exec|new\s+ProcessBuilder)\s*\(")
_JAVA_PATH_INPUT = re.compile(
    r"(?i)(?:\b(?:Path\.of|Paths\.get)\s*\([^)]*,\s*|\.resolve\(\s*)"
    r"(?:user|input|request|file|path)[A-Za-z0-9_$]*\s*\)"
)


def find_security_issues(repository: Path, paths: list[str]) -> list[Finding]:
    """Find high-confidence dangerous execution APIs in changed source files."""
    findings: list[Finding] = []
    repository_root = repository.resolve()
    for relative_path in paths:
        # A Git diff can contain a symlink.  Never follow it outside the
        # materialized review tree while performing a supposedly local scan.
        path = (repository / relative_path).resolve()
        if not path.is_relative_to(repository_root):
            continue
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        findings.extend(_secret_findings(path, relative_path))
        if suffix in {".py", ".pyi"}:
            findings.extend(_python_findings(path, relative_path))
        elif suffix in {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"}:
            findings.extend(_javascript_findings(path, relative_path))
        elif suffix == ".java":
            findings.extend(_java_findings(path, relative_path))
    return findings


def _python_findings(path: Path, relative_path: str) -> list[Finding]:
    source = path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(source, filename=relative_path)
    except SyntaxError:
        # Syntax is a linter concern; do not hide other valid-file findings behind it.
        return []

    visitor = _PythonSecurityVisitor(relative_path)
    visitor.visit(tree)
    return visitor.findings


class _PythonSecurityVisitor(ast.NodeVisitor):
    def __init__(self, path: str) -> None:
        self.path = path
        self.findings: list[Finding] = []
        self.aliases: dict[str, str] = {}

    def visit_Import(self, node: ast.Import) -> None:
        for imported in node.names:
            local_name = imported.asname or imported.name.split(".", maxsplit=1)[0]
            self.aliases[local_name] = imported.name

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module is None:
            return
        for imported in node.names:
            if imported.name == "*":
                continue
            self.aliases[imported.asname or imported.name] = f"{node.module}.{imported.name}"

    def visit_Call(self, node: ast.Call) -> None:
        target = _expand_alias(_dotted_name(node.func), self.aliases)
        rule: tuple[str, str, str] | None = None
        if target in {"eval", "exec", "builtins.eval", "builtins.exec"}:
            rule = (
                "dynamic-execution",
                f"Avoid {target.rsplit('.', 1)[-1]} on untrusted input",
                "Dynamic execution can run arbitrary Python supplied by an attacker.",
            )
        elif target in {"os.system", "os.popen"}:
            rule = (
                "shell-execution",
                "Avoid shell execution with os",
                "Shell commands built from input can allow command injection.",
            )
        elif target in {"pickle.loads", "pickle.load", "marshal.loads", "marshal.load"}:
            rule = (
                "unsafe-deserialization",
                "Avoid deserializing untrusted Python objects",
                "Pickle and marshal payloads can execute code while being deserialized.",
            )
        elif target in {"subprocess.run", "subprocess.call", "subprocess.Popen"} and any(
            keyword.arg == "shell"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value is True
            for keyword in node.keywords
        ):
            rule = (
                "shell-true",
                "Avoid subprocess shell=True",
                "shell=True can allow command injection when arguments include untrusted input.",
            )

        if rule is not None:
            self.findings.append(_finding(self.path, node.lineno, *rule))
        self.generic_visit(node)


def _javascript_findings(path: Path, relative_path: str) -> list[Finding]:
    source = path.read_text(encoding="utf-8", errors="replace")
    return [
        _finding(
            relative_path,
            source.count("\n", 0, match.start()) + 1,
            "dynamic-execution",
            f"Avoid JavaScript {match.group('name')} execution",
            "Dynamic JavaScript execution can run attacker-controlled code.",
        )
        for match in _JAVASCRIPT_CALLS.finditer(source)
    ]


def _secret_findings(path: Path, relative_path: str) -> list[Finding]:
    source = path.read_text(encoding="utf-8", errors="replace")
    return [
        _finding(
            relative_path,
            source.count("\n", 0, match.start()) + 1,
            "hardcoded-secret",
            "Remove the hardcoded credential",
            "A credential-like value is embedded in source. Rotate it and load it "
            "from a secret store.",
        )
        for match in _SECRET_ASSIGNMENT.finditer(source)
    ]


def _java_findings(path: Path, relative_path: str) -> list[Finding]:
    source = path.read_text(encoding="utf-8", errors="replace")
    rules = (
        (
            _JAVA_SQL_CONCAT,
            "java-sql-concatenation",
            "Use a parameterized SQL statement",
            "Concatenating values into a SQL execution call can allow SQL injection.",
        ),
        (
            _JAVA_SQL_VARIABLE_CONCAT,
            "java-sql-concatenation",
            "Use a parameterized SQL statement",
            "Building a SQL variable by concatenating values can allow SQL injection.",
        ),
        (
            _JAVA_COMMAND,
            "java-command-execution",
            "Avoid commands assembled from untrusted input",
            "Runtime command construction can allow command injection.",
        ),
        (
            _JAVA_PATH_INPUT,
            "java-path-boundary",
            "Validate the resolved path remains inside its allowed root",
            "A variable path segment must be normalized and checked against the allowed root.",
        ),
    )
    return [
        _finding(
            relative_path,
            source.count("\n", 0, match.start()) + 1,
            rule_id,
            title,
            rationale,
        )
        for pattern, rule_id, title, rationale in rules
        for match in pattern.finditer(source)
    ]


def _dotted_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _dotted_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return None


def _expand_alias(target: str | None, aliases: dict[str, str]) -> str | None:
    if target is None:
        return None
    root, dot, remainder = target.partition(".")
    resolved = aliases.get(root, root)
    return f"{resolved}.{remainder}" if dot else resolved


def _finding(path: str, line: int, rule_id: str, title: str, rationale: str) -> Finding:
    return Finding(
        severity=Severity.CRITICAL,
        category=Category.SECURITY,
        title=title,
        description=rationale,
        rationale=rationale,
        file=path.replace("\\", "/"),
        line_start=max(1, line),
        source=FindingSource.SECURITY,
        rule_id=rule_id,
        confidence=0.98,
    )
