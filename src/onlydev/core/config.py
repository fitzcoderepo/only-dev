from __future__ import annotations

from pathlib import Path
import json

CONFIG_PATH = Path(__file__).parent.parent.parent.parent / "config.json"


def load_config() -> dict:
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def save_config(config: dict) -> None:
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=4)


def get(section: str) -> dict:
    return load_config()[section]