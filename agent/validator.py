"""
Pydantic models for structured input/output validation.

Defines the data contracts used across the agent:
- ThoughtProcess: LLM's internal reasoning
- ToolCall: A tool invocation request
- AgentResponse: Full LLM response (thought + tool + is_final)
- ExecutionResult: Script execution result
- AgentFinalOutput: Final structured output for the user
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Gemini Schema Helper
# ---------------------------------------------------------------------------

def _strip_additional_properties(obj: Any) -> None:
    """Recursively strip 'additionalProperties' from a JSON schema dict."""
    if isinstance(obj, dict):
        obj.pop("additionalProperties", None)
        for value in obj.values():
            _strip_additional_properties(value)
    elif isinstance(obj, list):
        for item in obj:
            _strip_additional_properties(item)


def clean_schema_for_gemini(model_class: type[BaseModel]) -> dict:
    """
    Generate a JSON schema from a Pydantic model that is compatible
    with the Gemini API (no 'additionalProperties' anywhere).

    Args:
        model_class: The Pydantic model class.

    Returns:
        A cleaned JSON schema dict safe for Gemini's response_schema.
    """
    schema = model_class.model_json_schema()
    _strip_additional_properties(schema)
    return schema


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ToolName(str, Enum):
    """Supported tool names."""
    WRITE_FILE = "write_file"
    READ_FILE = "read_file"
    EXECUTE_SCRIPT = "execute_script"


# ---------------------------------------------------------------------------
# Agent Models
# ---------------------------------------------------------------------------

class ThoughtProcess(BaseModel):
    """The LLM's internal reasoning about the current step."""
    observation: str = Field(
        description="What the agent observes about the current state or user request."
    )
    plan: list[str] = Field(
        default_factory=list,
        description="Step-by-step plan of actions to accomplish the goal."
    )
    self_correction: Optional[str] = Field(
        default=None,
        description="Any self-correction or adjustment to the previous approach."
    )


class ToolArguments(BaseModel):
    """
    Flat argument model for tool calls.

    Uses explicit fields instead of a free-form dict to ensure
    Gemini-compatible JSON schema generation.
    """
    filename: Optional[str] = Field(
        default=None,
        description="The name of the file to create, read, or execute."
    )
    content: Optional[str] = Field(
        default=None,
        description="The content to write to the file (for write_file)."
    )
    timeout: Optional[int] = Field(
        default=None,
        description="Timeout in seconds for script execution (for execute_script)."
    )


class ToolCall(BaseModel):
    """A request to invoke a specific tool."""
    name: ToolName = Field(
        description="The name of the tool to invoke."
    )
    arguments: ToolArguments = Field(
        default_factory=ToolArguments,
        description="Arguments to pass to the tool."
    )


class AgentResponse(BaseModel):
    """
    Full structured response from the LLM.

    Contains the reasoning process, an optional tool call,
    and a flag indicating whether the task is complete.
    """
    thought: ThoughtProcess = Field(
        description="The agent's reasoning about the current step."
    )
    tool_call: Optional[ToolCall] = Field(
        default=None,
        description="The tool to invoke, if any. None when is_final=True."
    )
    is_final: bool = Field(
        default=False,
        description="Whether the agent considers the task complete."
    )
    final_summary: Optional[str] = Field(
        default=None,
        description="A summary of what the agent accomplished. Present when is_final=True."
    )


# ---------------------------------------------------------------------------
# Execution / Output Models
# ---------------------------------------------------------------------------

class ExecutionResult(BaseModel):
    """Result of executing a Python script."""
    stdout: str = Field(default="", description="Standard output from the script.")
    stderr: str = Field(default="", description="Standard error from the script.")
    exit_code: int = Field(description="Exit code of the script process.")


class AgentFinalOutput(BaseModel):
    """Final structured output returned to the user."""
    status: str = Field(description="'success' or 'error'.")
    output: str = Field(default="", description="Combined meaningful output.")
    error: str = Field(default="", description="Error message, if any.")
    exit_code: int = Field(default=0, description="Final exit code.")
