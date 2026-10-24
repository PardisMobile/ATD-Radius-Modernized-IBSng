"""Operator-invoked worker for durable mailbox cleanup jobs."""
from __future__ import annotations

import argparse
import sys

from atd_radius.config import settings
from atd_radius.infrastructure.db import connection
from atd_radius.infrastructure.mailbox_cleanup import process_pending_mailbox_cleanup


def main() -> int:
    parser = argparse.ArgumentParser(description="Process pending ATD Radius mailbox cleanup jobs")
    parser.add_argument("--limit", type=int, default=25, help="maximum jobs to process (1-500)")
    parser.add_argument("--timeout", type=int, default=15, help="per-command timeout in seconds (1-120)")
    args = parser.parse_args()
    try:
        with connection() as conn:
            succeeded, failed = process_pending_mailbox_cleanup(
                conn, settings.mailbox_cleanup_command, limit=args.limit, timeout_seconds=args.timeout
            )
    except (ValueError, OSError) as exc:
        print(f"mailbox cleanup worker: {exc}", file=sys.stderr)
        return 2
    print(f"mailbox cleanup batch complete: succeeded={succeeded} failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
