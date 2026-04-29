"""Graph generator functions — re-exports from ``networkx.generators``.

br-r37-c1-j54tp: previously a docstring-only module. Drop-in code that
did ``import franken_networkx.generators as g; g.balanced_tree(...)``
or ``from franken_networkx.generators import balanced_tree`` failed —
the empty submodule shadowed the package-level ``__getattr__`` fallback
even though ``franken_networkx.balanced_tree`` worked fine.

Re-exports every public name from ``networkx.generators`` (eagerly via
star-import for the common direct-attribute case), and also exposes
NetworkX's nested submodules (``classic``, ``random_graphs``, etc.) via
a fall-through ``__getattr__`` so imports like
``franken_networkx.generators.classic.balanced_tree`` resolve
transparently.
"""

from networkx.generators import *  # noqa: F401, F403


def __getattr__(name):
    """Fall through to ``networkx.generators`` for any name the
    star-import didn't pick up (notably nested submodules like
    ``classic`` that aren't auto-imported)."""
    import networkx.generators as _src

    try:
        return getattr(_src, name)
    except AttributeError as exc:
        raise AttributeError(
            f"module {__name__!r} has no attribute {name!r}"
        ) from exc


def __dir__():
    import networkx.generators as _src

    return sorted(set(globals()) | set(dir(_src)))
