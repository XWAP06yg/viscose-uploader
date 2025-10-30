"""
Viscose CLI package.

Provides a high-level command line interface for configuring and running the
Viscose Benchmarks uploader.
"""

__all__ = ["main", "__version__"]

from .cli import main  # noqa: F401
from .version import __version__  # noqa: F401
