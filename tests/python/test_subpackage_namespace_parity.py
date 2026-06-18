"""Parity tests for the ``franken_networkx.{generators,classes,algorithms}``
subpackages.

br-r37-c1-j54tp: prior to the fix, these three subpackages had empty
``__init__.py`` files (just a docstring). Drop-in code that did
``import franken_networkx.generators as g; g.balanced_tree(...)`` or
``from franken_networkx.algorithms import shortest_path`` failed —
the empty subpackage shadowed the package-level ``__getattr__`` fallback.

Pairs with ``test_exception_submodule_parity.py`` (br-r37-c1-md9br) to
cover the remaining four nx-mirror submodule paths.
"""

import importlib

import networkx as nx


SUBPACKAGES = [
    ("franken_networkx.generators", "networkx.generators"),
    ("franken_networkx.classes", "networkx.classes"),
    ("franken_networkx.algorithms", "networkx.algorithms"),
]

MODULE_EXPORTS = [
    ("franken_networkx.approximation", "networkx.algorithms.approximation"),
    ("franken_networkx.components", "networkx.algorithms.components"),
    ("franken_networkx.connectivity", "networkx.algorithms.connectivity"),
    ("franken_networkx.flow", "networkx.algorithms.flow"),
    ("franken_networkx.operators", "networkx.algorithms.operators"),
    ("franken_networkx.tournament", "networkx.algorithms.tournament"),
    ("franken_networkx.traversal", "networkx.algorithms.traversal"),
    ("franken_networkx.tree", "networkx.algorithms.tree"),
]


def _expected_exports(module):
    exports = getattr(module, "__all__", None)
    if exports:
        return set(exports)
    return {name for name in dir(module) if not name.startswith("_")}


def test_subpackage_direct_attribute_access_works():
    """Functions reachable on nx.<sub>.X must also be reachable on
    fnx.<sub>.X (by direct attribute access, not just via the parent
    package's __getattr__ fallback)."""
    fnx_gens = importlib.import_module("franken_networkx.generators")
    fnx_cls = importlib.import_module("franken_networkx.classes")
    fnx_algos = importlib.import_module("franken_networkx.algorithms")

    # Sample one well-known name from each
    assert hasattr(fnx_gens, "balanced_tree"), (
        "franken_networkx.generators.balanced_tree should resolve"
    )
    assert hasattr(fnx_cls, "add_cycle"), (
        "franken_networkx.classes.add_cycle should resolve"
    )
    assert hasattr(fnx_algos, "shortest_path"), (
        "franken_networkx.algorithms.shortest_path should resolve"
    )


def test_nested_submodule_access_falls_through_to_networkx():
    """``fnx.generators.classic``, ``fnx.algorithms.approximation``, etc.
    must resolve via __getattr__ fall-through.  Without this, code that
    walks the nx submodule tree explicitly breaks even though the top
    level works.

    br-r37-c1-qhcc2 (cousin to br-r37-c1-x5oxs): the resolved module
    is either an ``is``-identical nx submodule OR an fnx overlay /
    native module — fnx legitimately wraps several submodules
    (``franken_networkx.generators._register_franken_generator_submodules``
    builds an overlay proxy; ``franken_networkx.approximation`` is a
    native module returning fnx graph types).  Lock the documented
    fall-through contract without forcing strict ``is nx`` identity.
    """
    fnx_gens = importlib.import_module("franken_networkx.generators")
    fnx_algos = importlib.import_module("franken_networkx.algorithms")

    classic = fnx_gens.classic
    assert (
        classic is nx.generators.classic
        or classic.__name__.startswith("franken_networkx")
    ), (
        "fnx.generators.classic should alias nx.generators.classic or "
        f"an fnx overlay/native module, got {classic!r}"
    )
    approximation = fnx_algos.approximation
    assert (
        approximation is nx.algorithms.approximation
        or approximation.__name__.startswith("franken_networkx")
    ), (
        "fnx.algorithms.approximation should alias nx.algorithms.approximation"
        f" or an fnx-native module, got {approximation!r}"
    )


def test_subpackage_callable_invocation_smoke():
    """Round-trip a tiny call through each subpackage to verify the
    re-exported function actually executes."""
    fnx_gens = importlib.import_module("franken_networkx.generators")
    fnx_algos = importlib.import_module("franken_networkx.algorithms")

    tree = fnx_gens.balanced_tree(2, 2)
    assert tree.number_of_nodes() == 7

    sp = fnx_algos.shortest_path(tree, 0, 6)
    assert sp[0] == 0 and sp[-1] == 6


def test_dir_exposes_nx_sub_namespace():
    """``dir(fnx.<sub>)`` should list the same public names as
    ``dir(nx.<sub>)`` so introspection (autocomplete, help()) works."""
    for fnx_name, nx_name in SUBPACKAGES:
        fnx_mod = importlib.import_module(fnx_name)
        nx_mod = importlib.import_module(nx_name)
        nx_public = {n for n in dir(nx_mod) if not n.startswith("_")}
        fnx_public = {n for n in dir(fnx_mod) if not n.startswith("_")}
        missing = nx_public - fnx_public
        assert not missing, (
            f"{fnx_name} dir() missing public names also exposed by "
            f"{nx_name}: {sorted(missing)}"
        )


def test_overlay_modules_define_star_exports_like_networkx():
    for fnx_name, nx_name in MODULE_EXPORTS:
        fnx_mod = importlib.import_module(fnx_name)
        nx_mod = importlib.import_module(nx_name)
        expected = _expected_exports(nx_mod)

        assert set(fnx_mod.__all__) == expected
        missing_attrs = sorted(name for name in expected if not hasattr(fnx_mod, name))
        assert not missing_attrs, (
            f"{fnx_name} __all__ lists names not present on module: {missing_attrs}"
        )
