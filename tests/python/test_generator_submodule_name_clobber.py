"""A generator submodule must not clobber the function that shares its name.

FOUND while auditing br-r37-c1-3f37f. That bead's guard
(``test_child_module_clobber_audit.py``) covers the clobber class for the
ALGORITHMS members — it parses the ``_alias_nx_child_modules("networkx.
algorithms.X")`` call sites out of the algorithms package. ``generators`` is
aliased by a different mechanism, so it was outside that guard's scope, and
three live instances of the same class survived there.

THE SHAPE. ``franken_networkx/generators/__init__.py`` star-imports
``networkx.generators`` and then registers a proxy module for each nested
networkx submodule, binding it into ``globals()``. Three networkx generator
submodules share their name with the function they export — ``interval_graph``,
``nonisomorphic_trees`` and ``spectral_graph_forge``. networkx's own
``__init__`` imports the submodule and THEN runs ``from .interval_graph import
*``, so ``nx.generators.interval_graph`` is the FUNCTION. fnx's unconditional
rebinding put the proxy module back on top, and a module is not callable:

    nx.generators.interval_graph([(1, 2), (3, 4)])   -> Graph with 2 nodes
    fnx.generators.interval_graph([(1, 2), (3, 4)])  -> TypeError:
                                                        'module' object is not callable

The fix binds the attribute only where networkx binds a module there itself,
and leaves the ``sys.modules`` registration unconditional so
``import franken_networkx.generators.interval_graph`` keeps working — the same
duality networkx has.

The sweep below is deliberately wider than the three known names: it walks
every submodule fnx mirrors, so the next member to acquire a name collision is
caught without anyone remembering to extend a list.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil

import networkx as nx
import pytest

import franken_networkx as fnx

NAME_COLLIDING_GENERATORS = [
    "interval_graph",
    "nonisomorphic_trees",
    "spectral_graph_forge",
]


@pytest.mark.parametrize("name", NAME_COLLIDING_GENERATORS)
def test_generator_sharing_its_submodule_name_is_callable(name):
    """The regression pin. Before the fix each of these was a proxy module."""
    assert inspect.ismodule(
        importlib.import_module(f"networkx.generators.{name}")
    ), f"networkx layout changed: no networkx.generators.{name} submodule"
    assert callable(getattr(nx.generators, name)), (
        f"networkx changed: nx.generators.{name} is no longer the function, "
        "so this collision no longer exists and the pin needs revisiting"
    )
    value = getattr(fnx.generators, name)
    assert callable(value), f"fnx.generators.{name} is {type(value).__name__}"
    assert not inspect.ismodule(value)


def test_interval_graph_result_matches_networkx():
    """Callable is necessary but not sufficient — it must be the right callable."""
    intervals = [(1, 2), (3, 4), (2, 3)]
    got = fnx.generators.interval_graph(intervals)
    want = nx.generators.interval_graph(intervals)
    assert sorted(got.nodes()) == sorted(want.nodes())
    assert {frozenset(e) for e in got.edges()} == {frozenset(e) for e in want.edges()}
    assert type(got).__module__.startswith("franken_networkx"), (
        "the overlay must still hand back an fnx graph, not a bare nx one"
    )


def test_nonisomorphic_trees_matches_networkx():
    for order in (4, 5, 6, 7):
        got = [
            sorted(sorted(e) for e in t.edges())
            for t in fnx.generators.nonisomorphic_trees(order)
        ]
        want = [
            sorted(sorted(e) for e in t.edges())
            for t in nx.generators.nonisomorphic_trees(order)
        ]
        assert got == want, order


@pytest.mark.parametrize("name", NAME_COLLIDING_GENERATORS)
def test_the_submodule_import_path_still_resolves(name):
    """The fix must not buy callability by dropping the proxy module.

    networkx supports both spellings and so must fnx, which is why the
    sys.modules registration stayed unconditional while only the attribute
    binding became conditional.
    """
    module = importlib.import_module(f"franken_networkx.generators.{name}")
    assert inspect.ismodule(module)
    assert callable(getattr(module, name))


def test_nested_generator_proxies_are_still_modules():
    """The control: names networkx binds as MODULES must stay proxy modules."""
    for name in ("classic", "random_graphs", "lattice"):
        assert inspect.ismodule(getattr(nx.generators, name)), f"nx changed: {name}"
        proxy = getattr(fnx.generators, name)
        assert inspect.ismodule(proxy), f"{name} must still be a proxy module"
    assert callable(fnx.generators.classic.balanced_tree)


def _mirrored_submodules():
    """(name, fnx module, nx module) for every submodule fnx mirrors."""
    names = [info.name for info in pkgutil.iter_modules(fnx.__path__)]
    names += [
        "algorithms." + info.name
        for info in pkgutil.iter_modules(fnx.algorithms.__path__)
    ]
    pairs = []
    for name in sorted(set(names)):
        if name.startswith("_") or name == "tests":
            continue
        try:
            fmod = importlib.import_module(f"franken_networkx.{name}")
        except Exception:  # noqa: BLE001 - optional third-party deps
            continue
        for path in (f"networkx.{name}", f"networkx.algorithms.{name}"):
            try:
                pairs.append((name, fmod, importlib.import_module(path)))
                break
            except Exception:  # noqa: BLE001
                continue
    return pairs


MIRRORED = _mirrored_submodules()


def _public_callables(nmod):
    exported = getattr(nmod, "__all__", None)
    names = exported or [n for n in dir(nmod) if not n.startswith("_")]
    return [
        attr
        for attr in names
        if (value := getattr(nmod, attr, None)) is not None
        and not inspect.ismodule(value)
        and callable(value)
    ]


@pytest.mark.parametrize(
    "modname,fmod,nmod", MIRRORED, ids=[row[0] for row in MIRRORED]
)
def test_no_networkx_callable_became_uncallable_anywhere(modname, fmod, nmod):
    """The class, swept across every mirrored submodule rather than a list.

    THE CONTRACT IS CALLABILITY, NOT MODULE-NESS, and the distinction is load
    bearing: ``franken_networkx.bridges`` is a module subclass defining
    ``__call__``, a deliberate earlier fix for this same class. It answers
    ``callable()`` and works at the call site, so it is correct even though it
    is a module. Asserting "not a module" would fail it for no user-visible
    reason. What a caller actually depends on is being able to call it.
    """
    broken = [
        (attr, type(getattr(fmod, attr)).__name__)
        for attr in _public_callables(nmod)
        if hasattr(fmod, attr) and not callable(getattr(fmod, attr))
    ]
    assert not broken, (
        f"franken_networkx.{modname} turned networkx callables into "
        f"non-callables: {broken}"
    )


def test_bridges_is_the_known_callable_module():
    """Pins the one intentional module-that-is-callable, so it reads as chosen.

    If a later change makes this a plain function that is fine and this test
    should be updated. What must never happen is it becoming a NON-callable
    module, which the sweep above already forbids.
    """
    assert callable(fnx.bridges)
    assert list(fnx.bridges(nx.path_graph(4))) == list(nx.bridges(nx.path_graph(4)))


def test_the_sweep_is_not_vacuous():
    """A guard that scans nothing passes for the wrong reason."""
    assert len(MIRRORED) >= 20, f"only {len(MIRRORED)} mirrored submodules found"
    assert any(name == "generators" for name, _f, _n in MIRRORED), (
        "the sweep must reach `generators` — that is the member whose omission "
        "from the algorithms-scoped audit let this bug survive"
    )
    total = sum(len(_public_callables(nmod)) for _n, _f, nmod in MIRRORED)
    assert total >= 500, f"only {total} networkx callables checked"
