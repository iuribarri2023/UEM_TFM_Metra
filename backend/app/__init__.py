"""Inicialización del backend del Marketplace BIM."""

def create_app(overrides=None):
    from .factory import create_app as factory
    return factory(overrides)