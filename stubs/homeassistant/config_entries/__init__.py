"""Stub config_entries for tests."""
from dataclasses import dataclass, field


@dataclass
class ConfigEntry:
    entry_id: str = "test"
    data: dict = field(default_factory=dict)
    options: dict = field(default_factory=dict)
