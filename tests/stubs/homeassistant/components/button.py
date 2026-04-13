"""Stub for homeassistant.components.button."""


class ButtonEntity:
    """Stub ButtonEntity."""
    _attr_has_entity_name = False
    _attr_unique_id = None
    _attr_name = None
    _attr_icon = None

    @property
    def unique_id(self):
        return self._attr_unique_id

    @property
    def name(self):
        return self._attr_name

    @property
    def icon(self):
        return self._attr_icon
