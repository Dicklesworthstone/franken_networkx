"""Graph generator functions.

br-r37-c1-j54tp: previously a docstring-only module. Drop-in code that
did ``import franken_networkx.generators as g; g.balanced_tree(...)``
or ``from franken_networkx.generators import balanced_tree`` failed —
the empty submodule shadowed the package-level ``__getattr__`` fallback
even though ``franken_networkx.balanced_tree`` worked fine.

Start with every public name from ``networkx.generators`` (eagerly via
star-import for the common direct-attribute case), then overlay any
FrankenNetworkX top-level generator implementations so module-level
imports return fnx graph classes instead of pure NetworkX graphs. The
fall-through ``__getattr__`` still exposes NetworkX's nested submodules
(``classic``, ``random_graphs``, etc.) so imports like
``franken_networkx.generators.classic.balanced_tree`` resolve
transparently.
"""

from networkx.generators import *  # noqa: F401, F403


def _overlay_franken_generators():
    import sys

    parent = sys.modules.get("franken_networkx")
    if parent is None:
        return
    parent_globals = vars(parent)
    for name, value in tuple(globals().items()):
        if name.startswith("_") or not callable(value):
            continue
        replacement = parent_globals.get(name)
        if callable(replacement):
            globals()[name] = replacement


_overlay_franken_generators()


def __getattr__(name):
    """Fall through to ``networkx.generators`` for any name the
    star-import didn't pick up (notably nested submodules like
    ``classic`` that aren't auto-imported)."""
    import sys
    import networkx.generators as _src

    parent = sys.modules.get("franken_networkx")
    if parent is not None:
        parent_globals = vars(parent)
        if name in parent_globals:
            return parent_globals[name]

    try:
        return getattr(_src, name)
    except AttributeError as exc:
        raise AttributeError(
            f"module {__name__!r} has no attribute {name!r}"
        ) from exc


def __dir__():
    import networkx.generators as _src

    return sorted(set(globals()) | set(dir(_src)))
