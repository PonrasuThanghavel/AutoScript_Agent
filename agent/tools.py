"""
Tool layer for the AutoScript Agent.

Provides three tools:
- write_file: Create or overwrite a Python script
- read_file: Read contents of a file
- execute_script: Run a Python script via subprocess

All file operations are confined to a configurable workspace directory
(defaults to ./scripts/) for safety.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from agent.validator import ExecutionResult, ToolName


class ToolDispatcher:
    """
    Dispatches tool calls to the appropriate handler.

    All file operations are sandboxed within the specified workspace directory.
    """

    def __init__(self, workspace_dir: str = "scripts") -> None:
        """
        Initialize the tool dispatcher.

        Args:
            workspace_dir: Directory for script files (created if it doesn't exist).
        """
        self.workspace_dir = Path(workspace_dir).resolve()
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

    def dispatch(self, tool_name: ToolName, arguments: dict[str, Any]) -> str:
        """
        Dispatch a tool call to the appropriate handler.

        Args:
            tool_name: The tool to invoke.
            arguments: Key-value arguments for the tool.

        Returns:
            A string result describing what happened.

        Raises:
            ValueError: If the tool name is unknown.
        """
        handlers = {
            ToolName.WRITE_FILE: self._write_file,
            ToolName.READ_FILE: self._read_file,
            ToolName.EXECUTE_SCRIPT: self._execute_script,
        }

        handler = handlers.get(tool_name)
        if handler is None:
            raise ValueError(f"Unknown tool: {tool_name}")

        try:
            return handler(**arguments)
        except TypeError as e:
            return f"❌ Tool argument error: {str(e)}"

    def _resolve_path(self, filename: str) -> Path:
        """
        Resolve a filename to an absolute path within the workspace.

        Prevents path traversal attacks by ensuring the resolved path
        stays within the workspace directory.

        Args:
            filename: The filename or relative path.

        Returns:
            Resolved absolute path.

        Raises:
            ValueError: If the path escapes the workspace directory.
        """
        clean_name = str(filename).lstrip("/\\")
        resolved = (self.workspace_dir / clean_name).resolve()

        if not resolved.is_relative_to(self.workspace_dir):
            raise ValueError(
                f"Path traversal detected: '{filename}' resolves outside workspace."
            )

        return resolved

    def _write_file(self, filename: str, content: str) -> str:
        """
        Create or overwrite a file in the workspace directory.

        Args:
            filename: Name of the file to create.
            content: Content to write to the file.

        Returns:
            Confirmation message with the file path.
        """
        filepath = self._resolve_path(filename)
        filepath.write_text(content, encoding="utf-8")
        rel_path = filepath.relative_to(self.workspace_dir)
        return f"✅ File written successfully: {rel_path}"

    def _read_file(self, filename: str) -> str:
        """
        Read the contents of a file from the workspace directory.

        Args:
            filename: Name of the file to read.

        Returns:
            The file contents, or an error message if the file doesn't exist.
        """
        filepath = self._resolve_path(filename)

        if not filepath.exists():
            rel_path = filepath.relative_to(self.workspace_dir)
            return f"❌ File not found: {rel_path}"

        content = filepath.read_text(encoding="utf-8")
        rel_path = filepath.relative_to(self.workspace_dir)
        return f"📄 Contents of {rel_path}:\n{content}"

    def _execute_script(self, filename: str, timeout: int = 30) -> str:
        """
        Execute a Python script safely via subprocess.

        Args:
            filename: Name of the script to execute.
            timeout: Maximum execution time in seconds.

        Returns:
            Formatted string with stdout, stderr, and exit code.
        """
        if timeout is None:
            timeout = 30
            
        filepath = self._resolve_path(filename)

        if not filepath.exists():
            rel_path = filepath.relative_to(self.workspace_dir)
            return f"❌ Script not found: {rel_path}"

        try:
            result = subprocess.run(
                [sys.executable, str(filepath)],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self.workspace_dir),
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )

            execution = ExecutionResult(
                stdout=result.stdout.strip(),
                stderr=result.stderr.strip(),
                exit_code=result.returncode,
            )

        except subprocess.TimeoutExpired:
            execution = ExecutionResult(
                stdout="",
                stderr=f"⏰ Script timed out after {timeout} seconds.",
                exit_code=-1,
            )
        except Exception as e:
            execution = ExecutionResult(
                stdout="",
                stderr=f"💥 Execution error: {str(e)}",
                exit_code=-1,
            )

        # Format the result for the LLM
        parts = [f"🔄 Execution Result (exit code: {execution.exit_code}):"]
        if execution.stdout:
            parts.append(f"STDOUT:\n{execution.stdout}")
        if execution.stderr:
            parts.append(f"STDERR:\n{execution.stderr}")
        if not execution.stdout and not execution.stderr:
            parts.append("(no output)")

        return "\n".join(parts)
