from __future__ import annotations

import tomllib
from pathlib import Path

from .sorter import DEFAULT_ORDER

CONFIG_FILENAME = ".terraforder.toml"


class ConfigError(Exception):
    pass


def load_order(path: Path | None) -> tuple[str, ...]:
    """Read the block order from `path`, or from ./.terraforder.toml if it exists."""
    if path is None:
        path = Path(CONFIG_FILENAME)
        if not path.is_file():
            return DEFAULT_ORDER
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise ConfigError(f"{path}: {e}") from e

    unknown = sorted(set(data) - {"order"})
    if unknown:
        raise ConfigError(f"{path}: unknown setting(s): {', '.join(unknown)}")
    order = data.get("order", list(DEFAULT_ORDER))
    if not isinstance(order, list) or not all(isinstance(t, str) for t in order):
        raise ConfigError(f"{path}: 'order' must be a list of block type names")
    return tuple(order)
