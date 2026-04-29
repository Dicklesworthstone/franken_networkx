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
    must resolve via __getattr__ fall-through. Without this, code that
    walks the nx submodule tree explicitly breaks even though the top
    level works."""
    fnx_gens = importlib.import_module("franken_networkx.generators")
    fnx_algos = importlib.import_module("franken_networkx.algorithms")

    assert fnx_gens.classic is nx.generators.classic, (
        "fnx.generators.classic should alias nx.generators.classic"
    )
    assert fnx_algos.approximation is nx.algorithms.approximation, (
        "fnx.algorithms.approximation should alias nx.algorithms.approximation"
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
