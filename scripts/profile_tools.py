#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv

from reference_agent.service import ReferenceAgentService


def main() -> None:
    load_dotenv(".env.local")
    parser = argparse.ArgumentParser(description="Run tool profiling.")
    parser.add_argument("--profile", default="default", help="Profile ID to run profiling for")
    parser.add_argument("--force", action="store_true", help="Force re-profiling")
    parser.add_argument("--tool-id", action="append", dest="tool_ids", help="Limit to tool IDs")
    parser.add_argument(
        "--graph-schema-retry-max",
        type=int,
        default=5,
        help="Max retries for graph schema probe",
    )
    args = parser.parse_args()

    service = ReferenceAgentService(Path("config.yaml"), Path("tools/TOOLS.md"), Path("profiles"))
    service.prober.graph_schema_retry_max = args.graph_schema_retry_max
    rate_limit = service.config.runtime.rate_limit_per_base_url
    print(f"Profiling started (rate_limit_per_base_url={rate_limit})")

    def emit(event: dict) -> None:
        event_type = event.get("type")
        if event_type == "tool_started":
            tool_id = event.get("tool_id", "unknown")
            count = event.get("question_count", 0)
            print(f"[tool] start {tool_id} (questions={count})")
        elif event_type == "question_started":
            tool_id = event.get("tool_id", "unknown")
            idx = event.get("question_index", 0)
            question = event.get("question", "")
            print(f"[question] {tool_id} #{idx}: {question}")
        elif event_type == "question_retry":
            tool_id = event.get("tool_id", "unknown")
            idx = event.get("question_index", 0)
            attempt = event.get("attempt", 0)
            max_attempts = event.get("max_attempts", 0)
            reason = event.get("reason", "")
            print(f"[retry] {tool_id} #{idx} attempt {attempt}/{max_attempts} ({reason})")
        elif event_type == "tool_completed":
            tool_id = event.get("tool_id", "unknown")
            print(f"[tool] done {tool_id}")

    result = service.run_profiling(
        args.profile,
        force=args.force,
        tool_ids=args.tool_ids,
        progress_cb=emit,
    )
    print(f"Profiling completed: {result}")


if __name__ == "__main__":
    main()
