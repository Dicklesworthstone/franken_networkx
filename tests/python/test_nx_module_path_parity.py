"""Parity tests for the standalone fnx-mirror module paths.

br-r37-c1-hnv5y: ``networkx`` exposes 5 sub-paths that aren't real fnx
files — ``utils`` / ``linalg`` (subpackages), ``convert`` / ``relabel``
/ ``convert_matrix`` (modules). Before the fix, ``fnx.utils.X`` worked
via the package-level ``__getattr__`` fallback, but
``import franken_networkx.utils`` failed with ImportError because no
real submodule existed at that path.

Locks the contract: every nx public top-level submodule must be
directly importable through ``franken_networkx.<sub>`` and must surface
the same public names. Pairs with
``test_subpackage_namespace_parity.py`` (the original 4 nx-mirror
subpackages) and ``test_exception_submodule_parity.py``.
"""

import importlib

import networkx as nx
import franken_networkx as fnx


SUB_MODULES = ["utils", "linalg", "convert", "relabel", "convert_matrix"]


def test_each_module_path_is_directly_importable():
    """``import franken_networkx.<sub>`` must succeed for every nx
    top-level submodule."""
    for name in SUB_MODULES:
        mod = importlib.import_module(f"franken_networkx.{name}")
        assert mod is not None, f"franken_networkx.{name} did not import"


def test_from_import_works_for_each_module():
    """``from franken_networkx.<sub> import X`` works for the
    canonical entry-point name on each sub."""
    from franken_networkx.utils import discrete_sequence  # noqa: F401
    from franken_networkx.linalg import adjacency_matrix  # noqa: F401
    from franken_networkx.convert import to_dict_of_dicts  # noqa: F401
    from franken_networkx.relabel import relabel_nodes  # noqa: F401
    from franken_networkx.convert_matrix import to_numpy_array  # noqa: F401


def test_module_dir_covers_nx_public_names():
    """``dir(fnx.<sub>)`` should include every public name on
    ``nx.<sub>``."""
    for name in SUB_MODULES:
        fnx_mod = importlib.import_module(f"franken_networkx.{name}")
        nx_mod = importlib.import_module(f"networkx.{name}")
        nx_public = {n for n in dir(nx_mod) if not n.startswith("_")}
        fnx_public = {n for n in dir(fnx_mod) if not n.startswith("_")}
        missing = nx_public - fnx_public
        assert not missing, (
            f"franken_networkx.{name} dir() missing names also exposed "
            f"by networkx.{name}: {sorted(missing)[:5]}{'...' if len(missing) > 5 else ''}"
        )


def test_callables_actually_execute():
    """Round-trip a tiny call through each sub to verify the re-exported
    function actually executes (catches stale .pyc / cached-import
    issues that would let ``hasattr`` lie)."""
    G = fnx.path_graph(4)
    A = fnx.linalg.adjacency_matrix(G)
    assert A.shape == (4, 4)
    relabeled = fnx.relabel.relabel_nodes(G, {0: "a", 1: "b", 2: "c", 3: "d"})
    assert "a" in relabeled and "d" in relabeled
    arr = fnx.convert_matrix.to_numpy_array(G)
    assert arr.shape == (4, 4)


def test_aliases_against_nx_for_classlike_names():
    """For the nx-only classes / converters that pure fnx doesn't
    re-implement, each must alias the same nx object so isinstance
    checks across both libraries match."""
    import networkx.utils
    import networkx.linalg
    # GraphIterator-ish names (sample from nx.utils)
    for name in ("UnionFind", "PythonRandomInterface", "decorators"):
        if hasattr(nx.utils, name):
            assert getattr(fnx.utils, name) is getattr(nx.utils, name), (
                f"fnx.utils.{name} must alias nx.utils.{name}"
            )
