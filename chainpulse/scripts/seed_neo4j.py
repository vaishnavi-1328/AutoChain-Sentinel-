"""Seed Neo4j with ports from gazetteer + sample OEMs."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from chainpulse.backend.services.neo4j_writer import seed_minimal_supply_chain  # noqa: E402


def main() -> int:
    seed_minimal_supply_chain()
    print("✅ Neo4j seeded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
