"""Graph generator functions.

br-r37-c1-j54tp: previously a docstring-only module. Drop-in code that
did ``import franken_networkx.generators as g; g.balanced_tree(...)``
or ``from franken_networkx.generators import balanced_tree`` failed —
the empty submodule shadowed the package-level ``__getattr__`` fallback
even though ``franken_networkx.balanced_tree`` worked fine.

Start with every public name from ``networkx.generators`` (eagerly via
star-import for the common direct-attribute case), then overlay any
FrankenNetworkX top-level generator implementations so module-level and
nested-submodule imports return fnx graph classes instead of pure
NetworkX graphs. NetworkX's nested submodules (``classic``,
``random_graphs``, etc.) are proxied so imports like
``franken_networkx.generators.classic.balanced_tree`` resolve.
"""

from networkx.generators import *  # noqa: F401, F403


def _franken_parent_globals():
    import sys

    parent = sys.modules.get("franken_networkx")
    return {} if parent is None else vars(parent)


def _overlay_franken_generators(namespace):
    parent_globals = _franken_parent_globals()
    if not parent_globals:
        return
    for name, value in tuple(namespace.items()):
        if name.startswith("_") or not callable(value):
            continue
        replacement = parent_globals.get(name)
        if callable(replacement):
            namespace[name] = replacement


def _register_franken_generator_submodules():
    import importlib
    import pkgutil
    import sys
    import types
    import networkx.generators as _src

    modules = {}
    for name, value in tuple(vars(_src).items()):
        if isinstance(value, types.ModuleType) and value.__name__.startswith(
            "networkx.generators."
        ):
            modules[name] = value

    for info in pkgutil.iter_modules(_src.__path__):
        name = info.name
        if name == "tests" or name.startswith("_"):
            continue
        modules.setdefault(
            name, importlib.import_module(f"networkx.generators.{name}")
        )

    for name, source_module in modules.items():
        alias = f"{__name__}.{name}"
        proxy = types.ModuleType(alias, source_module.__doc__)
        proxy.__dict__.update(source_module.__dict__)
        proxy.__name__ = alias
        proxy.__package__ = __name__
        proxy.__spec__ = None
        _overlay_franken_generators(proxy.__dict__)
        sys.modules[alias] = proxy
        globals()[name] = proxy


_overlay_franken_generators(globals())
_register_franken_generator_submodules()


def __getattr__(name):
    """Fall through to ``networkx.generators`` for any name the
    star-import didn't pick up (notably nested submodules like
    ``classic`` that aren't auto-imported)."""
    import networkx.generators as _src

    parent_globals = _franken_parent_globals()
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
