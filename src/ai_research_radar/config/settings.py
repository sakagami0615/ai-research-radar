from __future__ import annotations

from dataclasses import dataclass
from datetime import timezone, tzinfo
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml

from ai_research_radar.periods import DEFAULT_MAX_LOOKBACK_DAYS


@dataclass(frozen=True)
class SourceConfig:
    name: str
    family: str
    adapter: str
    enabled: bool
    auth_required: bool
    options: dict[str, Any]


def load_yaml_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML object")
    return data


def load_source_configs(path: Path) -> list[SourceConfig]:
    data = load_yaml_config(path)
    sources = data.get("sources", {})
    configs: list[SourceConfig] = []
    for name, values in sources.items():
        options = dict(values)
        family = str(options.pop("family"))
        adapter = str(options.pop("adapter"))
        enabled = bool(options.pop("enabled", True))
        auth_required = bool(options.pop("auth_required", False))
        configs.append(
            SourceConfig(
                name=str(name),
                family=family,
                adapter=adapter,
                enabled=enabled,
                auth_required=auth_required,
                options=options,
            )
        )
    return configs


def load_scoring_config(path: Path) -> dict[str, Any]:
    return load_yaml_config(path)


def load_runtime_config(path: Path) -> dict[str, Any]:
    return load_yaml_config(path)


def load_runtime_config_or_default(path: Path) -> dict[str, Any]:
    """runtime.yaml only holds defaults (directories, timezone, lookback days), so a
    missing or broken file falls back to them instead of stopping a command."""
    try:
        return load_runtime_config(path)
    except (OSError, ValueError, yaml.YAMLError):
        return {}


def resolve_output_dir(runtime: dict[str, Any], key: str, default: str) -> Path:
    """Return `output.<key>` (data_dir / reports_dir), or `default` unless it is a non-empty string."""
    section = runtime.get("output")
    value = section.get(key) if isinstance(section, dict) else None
    return Path(value) if isinstance(value, str) and value else Path(default)


def resolve_display_timezone(runtime: dict[str, Any]) -> tzinfo:
    """Return `runtime.timezone` for displaying report times. A missing or
    invalid name falls back to UTC so a config typo never blocks the report."""
    section = runtime.get("runtime")
    name = section.get("timezone") if isinstance(section, dict) else None
    if not isinstance(name, str):
        return timezone.utc
    try:
        return ZoneInfo(name)
    except (ValueError, LookupError, OSError):
        return timezone.utc


def resolve_max_lookback_days(runtime: dict[str, Any]) -> int:
    """Return `collection.max_lookback_days`. Anything but a positive integer
    falls back to the default so a config typo never blocks collection."""
    section = runtime.get("collection")
    value = section.get("max_lookback_days") if isinstance(section, dict) else None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return DEFAULT_MAX_LOOKBACK_DAYS
    return value
