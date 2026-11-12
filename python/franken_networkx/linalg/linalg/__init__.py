"""Nested compatibility alias for ``franken_networkx.linalg``."""

import franken_networkx.linalg as _parent
from franken_networkx.linalg import *  # noqa: F401,F403

__all__ = list(getattr(_parent, "__all__", ()))


def __getattr__(name):
    return getattr(_parent, name)


def __dir__():
    return dir(_parent)
