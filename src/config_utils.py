"""Utilities for loading project configuration files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_config(path: str) -> dict[str, Any]:
    """Load a YAML configuration file into a dictionary."""
    config_path = Path(path)

    with config_path.open("r", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file) or {}

    return config
