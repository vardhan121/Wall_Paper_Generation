from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
WALLPAPERS = DATA / "wallpapers"
DB = DATA / "memory.db"
CONFIG_PATH = ROOT / "config.json"

DATA.mkdir(exist_ok=True)
WALLPAPERS.mkdir(exist_ok=True)

with open(CONFIG_PATH, "r", encoding="utf-8") as config_file:
    CFG = json.load(config_file)
