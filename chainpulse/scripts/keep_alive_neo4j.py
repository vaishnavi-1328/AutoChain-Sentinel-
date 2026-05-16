"""Neo4j AuraDB Free keep-alive — pings every 12h to prevent 3-day idle pause.

Run as Render cron job.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from chainpulse.backend.db.neo4j import session  # noqa: E402


def main() -> int:
    try:
        with session() as s:
            rec = s.run("MATCH (n) RETURN count(n) AS c LIMIT 1").single()
            print(f"✓ neo4j alive, node count = {rec['c'] if rec else 0}")
        return 0
    except Exception as e:
        print(f"✗ neo4j ping failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
