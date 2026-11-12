"""Regression guard: every public callable on a *nested* NetworkX submodule
path must also be reachable on the matching ``franken_networkx`` path.

``test_subpackage_namespace_parity.py`` only checks the three immediate
subpackages (``generators`` / ``classes`` / ``algorithms``) via ``dir()`` and
spot-checks two nested modules for *module* resolution. It does NOT assert
that the functions living on *deeper* paths — e.g.
``algorithms.centrality.betweenness_centrality`` or
``algorithms.flow.maximum_flow`` — are individually reachable on the fnx side.

That deeper reachability is the known, twice-recurring "submodule re-export
gap" bug class: a subpackage's ``from networkx.X import *`` (or an empty/
overlay ``__init__``) silently drops dispatchable functions that are absent
from nx's ``__all__``, so ``fnx.algorithms.foo.bar`` raises ``AttributeError``
even though ``nx.algorithms.foo.bar`` resolves. It currently holds for all
~2700 functions across ~260 nested paths; this test locks that in so a future
submodule refactor (or a new nx release) can't quietly reintroduce the gap.
"""

import inspect

import networkx as nx
import franken_networkx as fnx

import pytest


# Roots whose nested submodule trees mirror nx's public algorithm surface.
_ROOTS = (
    "algorithms",
    "generators",
    "linalg",
    "operators",
    "community",
    "bipartite",
)


def _is_public_callable(obj):
    return callable(obj) and not inspect.isclass(obj) and not inspect.ismodule(obj)


def _collect_nx_surface():
    """Walk the nx submodule tree under each root, returning
    ``{submodule_path: sorted([public_function_names])}``.

    Recurses only into ``networkx``-owned submodules and guards against the
    cyclic re-exports nx uses (``algorithms`` re-exports ``shortest_paths``
    which re-exports back), keying the visited set on module identity.
    """
    seen_ids = set()
    surface = {}

    def walk(path, mod):
        if id(mod) in seen_ids:
            return
        seen_ids.add(id(mod))
        names = getattr(mod, "__all__", None) or [
            n for n in dir(mod) if not n.startswith("_")
        ]
        for name in names:
            try:
                obj = getattr(mod, name)
            except Exception:
                continue
            if inspect.ismodule(obj):
                if getattr(obj, "__name__", "").startswith("networkx"):
                    walk(f"{path}.{name}", obj)
            elif _is_public_callable(obj):
                surface.setdefault(path, set()).add(name)

    for root in _ROOTS:
        mod = getattr(nx, root, None)
        if mod is not None:
            walk(root, mod)
    return {p: sorted(names) for p, names in surface.items()}


_NX_SURFACE = _collect_nx_surface()


def _resolve_fnx_path(path):
    obj = fnx
    for part in path.split("."):
        if not hasattr(obj, part):
            return None
        obj = getattr(obj, part)
    return obj


def test_collected_surface_is_nontrivial():
    # Sanity: the walk must actually find the expected breadth, otherwise a
    # silent walk failure would make the parametrized test vacuously pass.
    assert len(_NX_SURFACE) >= 100
    assert sum(len(v) for v in _NX_SURFACE.values()) >= 1000


@pytest.mark.parametrize("path", sorted(_NX_SURFACE))
def test_nested_submodule_path_resolves_on_fnx(path):
    assert _resolve_fnx_path(path) is not None, (
        f"nx submodule path '{path}' has no counterpart reachable on "
        f"franken_networkx (broken __getattr__ fall-through or missing overlay)"
    )


@pytest.mark.parametrize("path", sorted(_NX_SURFACE))
def test_nested_submodule_callables_reachable_on_fnx(path):
    fnx_mod = _resolve_fnx_path(path)
    if fnx_mod is None:
        pytest.skip("path resolution covered by the dedicated test")
    missing = [name for name in _NX_SURFACE[path] if not hasattr(fnx_mod, name)]
    assert not missing, (
        f"functions on nx.{path} are not reachable on franken_networkx.{path}: "
        f"{missing}"
    )
