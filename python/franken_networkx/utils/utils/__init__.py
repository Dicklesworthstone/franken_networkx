"""Nested compatibility alias for ``franken_networkx.utils``."""

import franken_networkx.utils as _parent
from franken_networkx.utils import *  # noqa: F401,F403

__all__ = list(getattr(_parent, "__all__", ()))


def __getattr__(name):
    return getattr(_parent, name)


def __dir__():
    return dir(_parent)
