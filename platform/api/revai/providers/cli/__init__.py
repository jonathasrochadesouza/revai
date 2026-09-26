"""Local CLI provider adapters."""

from revai.providers.cli.claude_code import ClaudeCodeProvider
from revai.providers.cli.copilot import CopilotCliProvider
from revai.providers.cli.kiro import KiroCliProvider
from revai.providers.cli.opencode import OpencodeCliProvider

__all__ = ["ClaudeCodeProvider", "CopilotCliProvider", "KiroCliProvider", "OpencodeCliProvider"]
