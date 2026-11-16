"""Djangoer: a Studio for your Django models and their data."""

from importlib.metadata import PackageNotFoundError, version

try:
    # The version is written once, in pyproject.toml.
    __version__ = version("djangoer")
except PackageNotFoundError:  # a source tree that is not installed
    __version__ = "0.0.0"
