"""FastAPI surface for CodeCompass."""

from codecompass.api.app import create_app
from codecompass.api.runtime import APISettings

__all__ = ["APISettings", "create_app"]
