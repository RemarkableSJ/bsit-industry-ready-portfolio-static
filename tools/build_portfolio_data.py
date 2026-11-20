#!/usr/bin/env python3
"""Build the browser data file from data/portfolio.json."""
from pathlib import Path
import json
ROOT = Path(__file__).resolve().parents[1]
src = ROOT / "data" / "portfolio.json"
dst = ROOT / "assets" / "js" / "default-data.js"
data = json.loads(src.read_text(encoding="utf-8"))
if not isinstance(data.get("profile"), dict) or not isinstance(data.get("projects"), list):
    raise SystemExit("portfolio.json must contain a profile object and projects array")
dst.write_text("/* Generated from data/portfolio.json. Do not edit this generated file directly. */\nwindow.defaultPortfolio = " + json.dumps(data, ensure_ascii=False, indent=2) + ";\n", encoding="utf-8")
print(f"Updated {dst.relative_to(ROOT)}")
