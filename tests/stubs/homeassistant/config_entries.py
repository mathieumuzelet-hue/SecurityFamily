"""Stub for homeassistant.config_entries."""

from __future__ import annotations

from typing import Any


class ConfigEntry:
    """Minimal stub of a config entry."""

    def __init__(
        self,
        data: dict[str, Any] | None = None,
        options: dict[str, Any] | None = None,
    ) -> None:
        self.data: dict[str, Any] = data or {}
        self.options: dict[str, Any] = options or {}
        self.entry_id: str = "test_entry_id"


class ConfigFlow:
    """Minimal stub of ConfigFlow."""

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__()

    def __init__(self) -> None:
        self.hass: Any = None

    async def async_set_unique_id(self, unique_id: str) -> None:
        self._unique_id = unique_id

    def _abort_if_unique_id_configured(self) -> None:
        return None

    def async_show_form(self, **kwargs: Any) -> dict[str, Any]:
        return {"type": "form", **kwargs}

    def async_create_entry(self, **kwargs: Any) -> dict[str, Any]:
        return {"type": "create_entry", **kwargs}


class OptionsFlow:
    """Minimal stub of OptionsFlow."""

    def __init__(self) -> None:
        self.hass: Any = None

    def async_show_form(self, **kwargs: Any) -> dict[str, Any]:
        return {"type": "form", **kwargs}

    def async_create_entry(self, **kwargs: Any) -> dict[str, Any]:
        return {"type": "create_entry", **kwargs}
