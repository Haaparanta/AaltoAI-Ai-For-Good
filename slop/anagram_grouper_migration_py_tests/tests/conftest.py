from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIR = ROOT.parent / "anagram_grouper" / "source"
sys.path.insert(0, str(SOURCE_DIR))
