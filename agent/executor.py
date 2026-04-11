"""
Agent Executor — the main orchestration loop.

Implements the Reason → Plan → Act → Observe cycle:
1. Sends user request to the Planner (LLM)
2. Receives a structured AgentResponse with reasoning + tool call
3. Dispatches the tool call via ToolDispatcher
4. Feeds the result back to the Planner as an observation
5. Repeats until is_final=True or max iterations reached
"""

from __future__ import annotations

from typing import Optional

from agent.planner import Planner, RateLimitError
from agent.tools import ToolDispatcher
from agent.validator import AgentFinalOutput, AgentResponse


# ANSI color codes for terminal output
class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


class AgentExecutor:
    """
    Orchestrates the agent loop: Reason → Plan → Act → Observe.

    Coordinates between the LLM Planner and the Tool layer to
    autonomously complete user tasks.
    """

    def __init__(
        self,
        planner: Optional[Planner] = None,
        tools: Optional[ToolDispatcher] = None,
        max_iterations: int = 10,
        verbose: bool = True,
    ) -> None:
        """
        Initialize the executor.

        Args:
            planner: The LLM planner instance. Created with defaults if None.
            tools: The tool dispatcher instance. Created with defaults if None.
            max_iterations: Maximum number of Reason→Act cycles before stopping.
            verbose: Whether to print detailed step-by-step output.
        """
        self.planner = planner or Planner()
        self.tools = tools or ToolDispatcher()
        self.max_iterations = max_iterations
        self.verbose = verbose

    def _print_step_header(self, iteration: int) -> None:
        """Print a colored header for the current step."""
        if self.verbose:
            print(
                f"\n{Colors.BOLD}{Colors.HEADER}"
                f"{'━' * 60}"
                f"\n  🔄 Step {iteration}"
                f"\n{'━' * 60}"
                f"{Colors.RESET}"
            )

    def _print_thought(self, response: AgentResponse) -> None:
        """Print the agent's reasoning process."""
        if not self.verbose:
            return

        thought = response.thought
        print(f"\n{Colors.CYAN}{Colors.BOLD}  💭 Observation:{Colors.RESET}")
        print(f"  {Colors.DIM}{thought.observation}{Colors.RESET}")

        if thought.plan:
            print(f"\n{Colors.BLUE}{Colors.BOLD}  📋 Plan:{Colors.RESET}")
            for i, step in enumerate(thought.plan, 1):
                print(f"  {Colors.DIM}{i}. {step}{Colors.RESET}")

        if thought.self_correction:
            print(f"\n{Colors.YELLOW}{Colors.BOLD}  🔧 Self-Correction:{Colors.RESET}")
            print(f"  {Colors.DIM}{thought.self_correction}{Colors.RESET}")

    def _print_tool_call(self, response: AgentResponse) -> None:
        """Print the tool being invoked."""
        if not self.verbose or response.tool_call is None:
            return

        tc = response.tool_call
        print(f"\n{Colors.GREEN}{Colors.BOLD}  🛠️  Tool: {tc.name.value}{Colors.RESET}")

        args_dict = tc.arguments.model_dump(exclude_none=True)
        for key, value in args_dict.items():
            display_value = value
            if isinstance(value, str) and len(value) > 200:
                display_value = value[:200] + "... (truncated)"
            print(f"  {Colors.DIM}  {key}: {display_value}{Colors.RESET}")

    def _print_tool_result(self, result: str) -> None:
        """Print the result of a tool execution."""
        if not self.verbose:
            return

        print(f"\n{Colors.YELLOW}{Colors.BOLD}  📤 Result:{Colors.RESET}")
        # Indent result lines for readability
        for line in result.split("\n"):
            print(f"  {Colors.DIM}  {line}{Colors.RESET}")

    def _print_final(self, response: AgentResponse) -> None:
        """Print the final completion message."""
        if not self.verbose:
            return

        print(
            f"\n{Colors.BOLD}{Colors.GREEN}"
            f"{'━' * 60}"
            f"\n  ✅ Task Complete!"
            f"\n{'━' * 60}"
            f"{Colors.RESET}"
        )
        if response.final_summary:
            print(
                f"\n{Colors.GREEN}  📝 Summary: {response.final_summary}{Colors.RESET}"
            )

    def run(self, user_request: str) -> AgentFinalOutput:
        """
        Execute the agent loop for a given user request.

        Args:
            user_request: The natural language task to accomplish.

        Returns:
            AgentFinalOutput with the final status, output, and any errors.
        """
        # Reset planner history for a fresh task
        self.planner.reset()

        if self.verbose:
            print(
                f"\n{Colors.BOLD}{Colors.BLUE}"
                f"{'═' * 60}"
                f"\n  🚀 AutoScript Agent — Processing Request"
                f"\n{'═' * 60}"
                f"{Colors.RESET}"
                f'\n{Colors.DIM}  "{user_request}"{Colors.RESET}'
            )

        last_tool_result: Optional[str] = None
        last_execution_output = ""

        for iteration in range(1, self.max_iterations + 1):
            self._print_step_header(iteration)

            try:
                # Get next action from the LLM
                if iteration == 1:
                    response = self.planner.get_next_action(user_message=user_request)
                else:
                    response = self.planner.get_next_action(
                        tool_result=last_tool_result
                    )

                self._print_thought(response)

                # Check if the task is complete
                if response.is_final:
                    self._print_final(response)
                    return AgentFinalOutput(
                        status="success",
                        output=last_execution_output or (response.final_summary or ""),
                        error="",
                        exit_code=0,
                    )

                # Dispatch the tool call
                if response.tool_call is None:
                    # LLM didn't provide a tool call but also isn't final — nudge it
                    last_tool_result = (
                        "Error: Missing tool call. You must either output a valid "
                        "`tool_call` object with a supported tool name (e.g., 'write_file', "
                        "'read_file', 'execute_script') OR set `is_final=True` if you "
                        "have completed the user's request. Do not output empty tool calls."
                    )
                    continue

                self._print_tool_call(response)

                # Execute the tool
                tool_result = self.tools.dispatch(
                    response.tool_call.name,
                    response.tool_call.arguments.model_dump(exclude_none=True),
                )

                self._print_tool_result(tool_result)
                last_tool_result = tool_result

                # Track execution output for the final result
                if response.tool_call.name.value == "execute_script":
                    last_execution_output = tool_result

            except RateLimitError as e:
                # Rate limit / quota error — fail fast, don't waste iterations
                if self.verbose:
                    print(
                        f"\n{Colors.RED}{Colors.BOLD}"
                        f"{'━' * 60}"
                        f"\n  🚫 API Quota Error"
                        f"\n{'━' * 60}"
                        f"{Colors.RESET}"
                        f"\n{Colors.RED}  {e}{Colors.RESET}"
                    )
                return AgentFinalOutput(
                    status="error",
                    output="",
                    error=str(e),
                    exit_code=1,
                )

            except Exception as e:
                error_msg = (
                    f"❌ Error in step {iteration}: {type(e).__name__}: {str(e)}"
                )
                if self.verbose:
                    print(f"\n{Colors.RED}  {error_msg}{Colors.RESET}")

                # Feed the error back to the LLM for self-correction
                last_tool_result = error_msg

        # Max iterations reached
        if self.verbose:
            print(
                f"\n{Colors.RED}{Colors.BOLD}"
                f"{'━' * 60}"
                f"\n  ⚠️  Max iterations ({self.max_iterations}) reached!"
                f"\n{'━' * 60}"
                f"{Colors.RESET}"
            )

        return AgentFinalOutput(
            status="error",
            output=last_execution_output,
            error=f"Agent did not complete within {self.max_iterations} iterations.",
            exit_code=1,
        )
