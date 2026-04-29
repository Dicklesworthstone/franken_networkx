"""Graph classes — re-exports from ``networkx.classes``.

br-r37-c1-j54tp: see ``franken_networkx.generators`` docstring for the
parity-gap context. Same pattern: previously empty submodule that
broke ``import franken_networkx.classes as c; c.add_cycle(...)`` even
though ``franken_networkx.add_cycle`` worked.

Note: this re-exports nx's *Graph classes — the actual fnx Graph /
DiGraph / MultiGraph / MultiDiGraph used by user code remain the
fnx-native classes exposed at the top level of ``franken_networkx``.
``franken_networkx.classes`` is the *nx-mirror* path used by code that
explicitly imports through it for compatibility with nx-style
introspection.
"""

from networkx.classes import *  # noqa: F401, F403


def __getattr__(name):
    import networkx.classes as _src

    try:
        return getattr(_src, name)
    except AttributeError as exc:
        raise AttributeError(
            f"module {__name__!r} has no attribute {name!r}"
        ) from exc


def __dir__():
    import networkx.classes as _src

    return sorted(set(globals()) | set(dir(_src)))
