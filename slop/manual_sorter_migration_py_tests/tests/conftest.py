from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIR = ROOT.with_name("manual_sorter")
sys.path.insert(0, str(SOURCE_DIR))
