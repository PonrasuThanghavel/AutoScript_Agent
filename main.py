#!/usr/bin/env python3
"""
AutoScript Agent — CLI Entry Point.

An AI-powered Python agent that generates, executes, and captures
script outputs from natural language instructions.

Usage:
    Interactive mode:  python main.py
    One-shot mode:     python main.py "your task here"
"""

from __future__ import annotations

import json
import sys

from dotenv import load_dotenv

from agent.executor import AgentExecutor, Colors
from agent.planner import Planner
from agent.tools import ToolDispatcher
from agent.validator import AgentFinalOutput

BANNER = f"""
{Colors.BOLD}{Colors.CYAN}
    ╔═══════════════════════════════════════════════════╗
    ║                                                   ║
    ║   🚀  A U T O S C R I P T   A G E N T  🚀       ║
    ║                                                   ║
    ║   AI-Powered Python Script Generator & Executor   ║
    ║                                                   ║
    ╚═══════════════════════════════════════════════════╝
{Colors.RESET}
{Colors.DIM}  Powered by Google Gemini  •  Type 'quit' or 'exit' to stop
  Type 'help' for usage information{Colors.RESET}
"""

HELP_TEXT = f"""
{Colors.BOLD}{Colors.BLUE}  📖 AutoScript Agent — Help{Colors.RESET}

{Colors.CYAN}  Commands:{Colors.RESET}
    {Colors.DIM}help{Colors.RESET}          Show this help message
    {Colors.DIM}quit / exit{Colors.RESET}   Exit the agent
    {Colors.DIM}clear{Colors.RESET}         Clear conversation history

{Colors.CYAN}  Usage:{Colors.RESET}
    Just type a natural language instruction, for example:
    {Colors.GREEN}>>> Create a Python script that generates the first 20 Fibonacci numbers{Colors.RESET}
    {Colors.GREEN}>>> Write a script to fetch and display the current UTC time{Colors.RESET}
    {Colors.GREEN}>>> Create a script that sorts a list of names alphabetically{Colors.RESET}

{Colors.CYAN}  One-shot mode:{Colors.RESET}
    {Colors.DIM}python main.py "your task here"{Colors.RESET}
"""


def print_result(result: AgentFinalOutput) -> None:
    """Pretty-print the final structured output as JSON."""
    print(
        f"\n{Colors.BOLD}{Colors.BLUE}"
        f"{'═' * 60}"
        f"\n  📊 Structured Output"
        f"\n{'═' * 60}"
        f"{Colors.RESET}"
    )
    output_dict = result.model_dump()
    print(f"{Colors.DIM}{json.dumps(output_dict, indent=2)}{Colors.RESET}")


def run_interactive(executor: AgentExecutor) -> None:
    """Run the agent in interactive REPL mode."""
    print(BANNER)

    while True:
        try:
            user_input = input(
                f"\n{Colors.BOLD}{Colors.GREEN}  >>> {Colors.RESET}"
            ).strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Colors.DIM}  👋 Goodbye!{Colors.RESET}")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit"):
            print(f"{Colors.DIM}  👋 Goodbye!{Colors.RESET}")
            break

        if user_input.lower() == "help":
            print(HELP_TEXT)
            continue

        if user_input.lower() == "clear":
            executor.planner.reset()
            print(f"{Colors.DIM}  🧹 Conversation history cleared.{Colors.RESET}")
            continue

        # Run the agent
        result = executor.run(user_input)
        print_result(result)


def run_oneshot(executor: AgentExecutor, task: str) -> None:
    """Run the agent in one-shot mode with a single task."""
    result = executor.run(task)
    print_result(result)


def main() -> None:
    """Main entry point."""
    # Load environment variables from .env file
    load_dotenv()

    # Initialize components
    try:
        planner = Planner()
    except ValueError as e:
        print(f"\n{Colors.RED}{Colors.BOLD}  ❌ Configuration Error:{Colors.RESET}")
        print(f"{Colors.RED}  {e}{Colors.RESET}")
        print(
            f"\n{Colors.DIM}  💡 Create a .env file with: GOOGLE_API_KEY=your_key_here{Colors.RESET}"
        )
        print(
            f"{Colors.DIM}  💡 Or run: cp .env.example .env && edit .env{Colors.RESET}"
        )
        sys.exit(1)

    tools = ToolDispatcher(workspace_dir="scripts")
    executor = AgentExecutor(planner=planner, tools=tools)

    # Check for one-shot mode
    if len(sys.argv) > 1:
        task = " ".join(sys.argv[1:])
        run_oneshot(executor, task)
    else:
        run_interactive(executor)


if __name__ == "__main__":
    main()
