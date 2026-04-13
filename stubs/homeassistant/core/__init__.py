"""Stub core for tests."""
from dataclasses import dataclass, field


@dataclass
class HomeAssistant:
    data: dict = field(default_factory=dict)
