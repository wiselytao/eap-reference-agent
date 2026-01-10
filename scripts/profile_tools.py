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
    args = parser.parse_args()

    service = ReferenceAgentService(Path("config.yaml"), Path("tools/TOOLS.md"), Path("profiles"))
    result = service.run_profiling(args.profile, force=args.force, tool_ids=args.tool_ids)
    print(result)


if __name__ == "__main__":
    main()
