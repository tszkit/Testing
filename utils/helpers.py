"""Utility helpers."""
import logging
import sys
from pathlib import Path

from config.settings import LOG_DIR


def setup_logging(level: int = logging.INFO):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    logging.basicConfig(
        level=level,
        format=fmt,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(LOG_DIR / "trading.log"),
        ],
    )


def load_strategy_configs(path: Path) -> dict:
    import yaml
    with open(path) as f:
        return yaml.safe_load(f)
