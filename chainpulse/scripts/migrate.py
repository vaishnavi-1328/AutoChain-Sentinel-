"""Apply alembic migrations against current DATABASE_URL."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

# alembic.ini lives in chainpulse/
os.chdir(Path(__file__).resolve().parent.parent)

from alembic.config import Config  # noqa: E402
from alembic import command  # noqa: E402


def main() -> int:
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")
    print("✅ migrations applied")
    return 0


if __name__ == "__main__":
    sys.exit(main())
