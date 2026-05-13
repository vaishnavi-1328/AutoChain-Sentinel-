"""Make `chainpulse.backend.*` importable.

Repo dir is `chainpulse` (valid Python identifier), but lives under a parent
path with a space, so we register an alias namespace package whose __path__
is this directory. `from chainpulse.backend.main import app` resolves to
./backend/main.py.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parent

if "chainpulse" not in sys.modules:
    pkg = ModuleType("chainpulse")
    pkg.__path__ = [str(ROOT)]  # type: ignore[attr-defined]
    sys.modules["chainpulse"] = pkg
