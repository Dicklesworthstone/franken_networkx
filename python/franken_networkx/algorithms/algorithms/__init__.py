"""Nested compatibility alias for ``franken_networkx.algorithms``."""

import franken_networkx.algorithms as _parent
from franken_networkx.algorithms import *  # noqa: F401,F403

__all__ = list(getattr(_parent, "__all__", ()))


def __getattr__(name):
    return getattr(_parent, name)


def __dir__():
    return dir(_parent)
