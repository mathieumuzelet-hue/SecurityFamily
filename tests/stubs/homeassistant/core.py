"""Stub for homeassistant.core."""


class HomeAssistant:
    pass


class ServiceCall:
    def __init__(self, domain=None, service=None, data=None):
        self.domain = domain
        self.service = service
        self.data = data or {}
