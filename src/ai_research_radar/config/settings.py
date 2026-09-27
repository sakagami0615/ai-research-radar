from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


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
