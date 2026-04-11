"""
LLM Planner for the AutoScript Agent.

Handles all communication with the Google Gemini API:
- Maintains conversation history for multi-turn context
- Sends structured prompts with the agent's system instructions
- Returns validated AgentResponse objects via Pydantic schema enforcement
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Optional

from google import genai
from google.genai.types import Content, Part

from agent.validator import AgentResponse, clean_schema_for_gemini

# System prompt that defines the agent's behavior
SYSTEM_PROMPT = """\
You are AutoScript Agent — an autonomous Python engineering assistant.
Your job is to help users by generating, executing, and debugging Python scripts.

## WORKFLOW
1. Analyze the user's request carefully.
2. Create a clear step-by-step plan.
3. Use tools ONE AT A TIME to accomplish the goal.
4. After each tool result, observe the outcome and decide the next step.
5. If a script fails, analyze the error, hypothesize a fix, and update the script.
6. When the task is fully complete, set is_final=True and provide a final_summary.

## AVAILABLE TOOLS
- **write_file**: Create or update a Python script.
  Arguments: {"filename": "script_name.py", "content": "python code here"}

- **read_file**: Read the contents of an existing script.
  Arguments: {"filename": "script_name.py"}

- **execute_script**: Execute a Python script and capture its output.
  Arguments: {"filename": "script_name.py", "timeout": 30}

## RULES
1. Always write the script BEFORE executing it.
2. Use descriptive filenames (e.g., "fibonacci.py", not "script.py").
3. Include proper error handling in generated scripts.
4. If execution fails, read the error, fix the script, and retry.
5. Do NOT generate unsafe code (no rm -rf, no system modifications, no network attacks).
6. When done, set is_final=True and summarize what you accomplished in final_summary.
7. Each response must include a thought process with observation and plan.
8. Issue exactly ONE tool_call per response (or none if is_final=True).
"""


class RateLimitError(Exception):
    """Raised when the API quota is exhausted and retries are not possible."""

    def __init__(self, message: str, is_daily_limit: bool = False) -> None:
        super().__init__(message)
        self.is_daily_limit = is_daily_limit


class Planner:
    """
    LLM-powered planner that uses Google Gemini for reasoning and code generation.

    Maintains conversation history for multi-turn context and returns
    validated AgentResponse objects.
    """

    def __init__(
        self,
        model: str = "gemini-2.0-flash",
        api_key: Optional[str] = None,
        max_retries: int = 3,
    ) -> None:
        """
        Initialize the planner with a Gemini model.

        Args:
            model: The Gemini model to use.
            api_key: Google API key. Falls back to GOOGLE_API_KEY env var.

        Raises:
            ValueError: If no API key is provided or found in environment.
        """
        self.model = model
        self._api_key = api_key or os.environ.get("GOOGLE_API_KEY")

        if not self._api_key:
            raise ValueError(
                "No API key provided. Set GOOGLE_API_KEY environment variable "
                "or pass api_key to Planner()."
            )

        self.client = genai.Client(api_key=self._api_key)
        self.history: list[Content] = []
        self.max_retries = max_retries

        # Pre-compute the Gemini-compatible schema (no additionalProperties)
        self._response_schema = clean_schema_for_gemini(AgentResponse)

    def reset(self) -> None:
        """Clear the conversation history for a new task."""
        self.history = []

    def get_next_action(
        self,
        user_message: Optional[str] = None,
        tool_result: Optional[str] = None,
    ) -> AgentResponse:
        """
        Get the next action from the LLM.

        Either a user_message (new task) or a tool_result (observation from
        the previous tool call) should be provided.

        Args:
            user_message: A new user request to process.
            tool_result: The result of the previous tool call (observation).

        Returns:
            A validated AgentResponse with the LLM's next action.

        Raises:
            ValueError: If neither user_message nor tool_result is provided.
        """
        if user_message is None and tool_result is None:
            raise ValueError("Either user_message or tool_result must be provided.")

        # Build the new message
        if user_message is not None:
            self.history.append(Content(role="user", parts=[Part(text=user_message)]))
        elif tool_result is not None:
            # Feed the tool result back as a user message (observation)
            observation_text = f"[TOOL RESULT]\n{tool_result}"
            self.history.append(
                Content(role="user", parts=[Part(text=observation_text)])
            )

        # Call Gemini with structured output + automatic retry on rate limits
        response = self._call_with_retry()

        # Parse the JSON response manually (can't use response.parsed with a dict schema)
        agent_response = AgentResponse.model_validate_json(response.text)

        # Add the assistant's response to history for multi-turn context
        tight_json = agent_response.model_dump_json(exclude_none=True)
        self.history.append(Content(role="model", parts=[Part(text=tight_json)]))

        return agent_response

    def _call_with_retry(self):
        """
        Call the Gemini API with automatic retry and backoff for rate limits.

        Parses the retryDelay from the 429 response and waits accordingly.
        Detects daily quota exhaustion and fails fast.

        Returns:
            The API response.

        Raises:
            RateLimitError: If the daily quota is exhausted or retries are exceeded.
        """
        last_error = None

        for attempt in range(1, self.max_retries + 1):
            try:
                return self.client.models.generate_content(
                    model=self.model,
                    contents=self.history,
                    config={
                        "system_instruction": SYSTEM_PROMPT,
                        "response_mime_type": "application/json",
                        "response_schema": self._response_schema,
                        "temperature": 0.2,
                    },
                )
            except Exception as e:
                last_error = e

                # We only retry on 429 API errors
                if (
                    not isinstance(
                        e,
                        getattr(
                            genai,
                            "errors",
                            type("stub", (), {"APIError": type("none")}),
                        ).APIError,
                    )
                    and "429" not in str(e)
                    and "RESOURCE_EXHAUSTED" not in str(e)
                ):
                    raise

                is_api_error = hasattr(e, "code")
                if is_api_error and e.code != 429:
                    raise

                error_str = str(e)

                # Detect daily quota exhaustion — not retryable
                if "PerDayPerProject" in error_str:
                    raise RateLimitError(
                        "Daily API quota exhausted. Your free-tier daily limit has been "
                        "reached. Please wait until the quota resets (usually midnight PT) "
                        "or upgrade your Gemini API plan.",
                        is_daily_limit=True,
                    ) from e

                # Parse retry delay from error message
                wait_seconds = 15.0
                response_json = getattr(e, "response_json", None)
                parsed_delay = False
                if isinstance(response_json, dict):
                    details = response_json.get("error", {}).get("details", [])
                    for detail in details:
                        if "retryDelay" in detail:
                            try:
                                delay_str = detail["retryDelay"].rstrip("s")
                                wait_seconds = min(float(delay_str) + 1.0, 120.0)
                                parsed_delay = True
                                break
                            except ValueError:
                                pass
                if not parsed_delay:
                    wait_seconds = self._parse_retry_delay(error_str, fallback=15.0)

                if attempt < self.max_retries:
                    print(
                        f"  ⏳ Rate limited. Waiting {wait_seconds:.0f}s before "
                        f"retry {attempt}/{self.max_retries}..."
                    )
                    time.sleep(wait_seconds)
                else:
                    raise RateLimitError(
                        f"Rate limit exceeded after {self.max_retries} retries. "
                        f"Please wait a moment and try again.",
                        is_daily_limit=False,
                    ) from e

        # Should not reach here, but just in case
        raise last_error  # type: ignore[misc]

    @staticmethod
    def _parse_retry_delay(error_str: str, fallback: float = 15.0) -> float:
        """
        Parse the retryDelay from a Gemini 429 error message.

        Looks for patterns like 'Please retry in 14.311925397s' or
        'retryDelay": "14s"' in the error string.

        Args:
            error_str: The error message string.
            fallback: Default wait time if parsing fails.

        Returns:
            The number of seconds to wait.
        """
        # Try "Please retry in Xs" pattern
        match = re.search(r"retry in ([\d.]+)s", error_str)
        if match:
            return min(float(match.group(1)) + 1.0, 120.0)  # cap at 2 minutes

        # Try "retryDelay": "Xs" pattern
        match = re.search(r'"retryDelay":\s*"(\d+)s"', error_str)
        if match:
            return min(float(match.group(1)) + 1.0, 120.0)

        return fallback
