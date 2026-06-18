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
import numpy as np
import franken_networkx as fnx
import pytest


SUB_MODULES = ["utils", "linalg", "convert", "relabel", "convert_matrix"]
READWRITE_SUBMODULES = [
    "adjlist",
    "edgelist",
    "gexf",
    "gml",
    "graph6",
    "graphml",
    "json_graph",
    "json_graph.adjacency",
    "json_graph.cytoscape",
    "json_graph.node_link",
    "json_graph.tree",
    "leda",
    "multiline_adjlist",
    "pajek",
    "sparse6",
    "text",
]


def _expect(condition, message):
    if not condition:
        pytest.fail(message)


def _canonical_edges(graph):
    return sorted(tuple(sorted(edge)) for edge in graph.edges())


def test_each_module_path_is_directly_importable():
    """``import franken_networkx.<sub>`` must succeed for every nx
    top-level submodule."""
    for name in SUB_MODULES:
        mod = importlib.import_module(f"franken_networkx.{name}")
        _expect(mod is not None, f"franken_networkx.{name} did not import")


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
        _expect(not missing, (
            f"franken_networkx.{name} dir() missing names also exposed "
            f"by networkx.{name}: {sorted(missing)[:5]}{'...' if len(missing) > 5 else ''}"
        ))


def test_callables_actually_execute():
    """Round-trip a tiny call through each sub to verify the re-exported
    function actually executes (catches stale .pyc / cached-import
    issues that would let ``hasattr`` lie)."""
    G = fnx.path_graph(4)
    A = fnx.linalg.adjacency_matrix(G)
    _expect(A.shape == (4, 4), "adjacency_matrix shape must match graph order")
    relabeled = fnx.relabel.relabel_nodes(G, {0: "a", 1: "b", 2: "c", 3: "d"})
    _expect("a" in relabeled and "d" in relabeled, "relabel_nodes result is missing endpoints")
    arr = fnx.convert_matrix.to_numpy_array(G)
    _expect(arr.shape == (4, 4), "to_numpy_array shape must match graph order")


def test_convert_module_to_dict_helpers_match_networkx_values(monkeypatch):
    module = importlib.import_module("franken_networkx.convert")
    fg = fnx.Graph()
    ng = nx.Graph()
    for graph in (fg, ng):
        graph.add_edge("a", "b", weight=3, color="red")
        graph.add_edge("b", "c", weight=5, color="blue")
        graph.add_node("isolated")

    _expect(
        module.to_dict_of_dicts(fg, nodelist=["b", "a"], edge_data="edge")
        == nx.to_dict_of_dicts(ng, nodelist=["b", "a"], edge_data="edge"),
        "convert.to_dict_of_dicts nodelist/edge_data values must match networkx",
    )
    _expect(
        module.to_dict_of_lists(fg, nodelist=["b", "a"])
        == nx.to_dict_of_lists(ng, nodelist=["b", "a"]),
        "convert.to_dict_of_lists nodelist values must match networkx",
    )

    sentinel = object()

    def fake_to_dict_of_dicts(graph, nodelist=None, edge_data=None):
        _expect(graph is fg, "convert.to_dict_of_dicts must pass through the original graph")
        _expect(nodelist == ["b", "a"], "convert.to_dict_of_dicts must forward nodelist")
        _expect(edge_data == "edge", "convert.to_dict_of_dicts must forward edge_data")
        return sentinel

    def fake_to_dict_of_lists(graph, nodelist=None):
        _expect(graph is fg, "convert.to_dict_of_lists must pass through the original graph")
        _expect(nodelist == ["b", "a"], "convert.to_dict_of_lists must forward nodelist")
        return sentinel

    monkeypatch.setattr(fnx, "to_dict_of_dicts", fake_to_dict_of_dicts)
    monkeypatch.setattr(fnx, "to_dict_of_lists", fake_to_dict_of_lists)
    _expect(
        module.to_dict_of_dicts(fg, nodelist=["b", "a"], edge_data="edge")
        is sentinel,
        "convert.to_dict_of_dicts must route through fnx",
    )
    _expect(
        module.to_dict_of_lists(fg, nodelist=["b", "a"])
        is sentinel,
        "convert.to_dict_of_lists must route through fnx",
    )


def test_convert_matrix_module_to_numpy_array_matches_networkx_values():
    module = importlib.import_module("franken_networkx.convert_matrix")
    scipy_sparse = pytest.importorskip("scipy.sparse")
    fg = fnx.Graph()
    ng = nx.Graph()
    for graph in (fg, ng):
        graph.add_edge("a", "b", weight=2.5)
        graph.add_edge("b", "c", weight=4.0)
        graph.add_node("isolated")

    actual = module.to_numpy_array(
        fg, nodelist=["b", "a", "isolated"], weight="weight"
    )
    expected = nx.to_numpy_array(
        ng, nodelist=["b", "a", "isolated"], weight="weight"
    )

    _expect(
        module.to_numpy_array is fnx.to_numpy_array,
        "convert_matrix.to_numpy_array must route through fnx",
    )
    _expect(
        actual.tolist() == expected.tolist(),
        "convert_matrix.to_numpy_array weighted values must match networkx",
    )

    actual_sparse = module.to_scipy_sparse_array(
        fg,
        nodelist=["b", "a", "isolated"],
        dtype=float,
        weight="weight",
        format="csr",
    )
    expected_sparse = nx.to_scipy_sparse_array(
        ng,
        nodelist=["b", "a", "isolated"],
        dtype=float,
        weight="weight",
        format="csr",
    )

    _expect(
        module.to_scipy_sparse_array is fnx.to_scipy_sparse_array,
        "convert_matrix.to_scipy_sparse_array must route through fnx",
    )
    _expect(
        scipy_sparse.issparse(actual_sparse),
        "convert_matrix.to_scipy_sparse_array must return a scipy sparse array",
    )
    _expect(
        actual_sparse.toarray().tolist() == expected_sparse.toarray().tolist(),
        "convert_matrix.to_scipy_sparse_array weighted values must match networkx",
    )


def test_convert_matrix_module_graph_builders_preserve_fnx_type():
    module = importlib.import_module("franken_networkx.convert_matrix")
    scipy_sparse = pytest.importorskip("scipy.sparse")

    dense = np.array([[0, 2, 0], [0, 0, 3], [4, 0, 0]])
    dense_actual = module.from_numpy_array(
        dense, create_using=fnx.DiGraph(), nodelist=["a", "b", "c"]
    )
    dense_expected = nx.from_numpy_array(
        dense, create_using=nx.DiGraph(), nodelist=["a", "b", "c"]
    )

    _expect(
        module.from_numpy_array is fnx.from_numpy_array,
        "convert_matrix.from_numpy_array must route through fnx",
    )
    _expect(
        isinstance(dense_actual, fnx.DiGraph),
        "convert_matrix.from_numpy_array must return an fnx DiGraph",
    )
    _expect(
        list(dense_actual.edges(data=True))
        == list(dense_expected.edges(data=True)),
        "convert_matrix.from_numpy_array edge data must match networkx",
    )

    sparse = scipy_sparse.csr_array(dense)
    sparse_actual = module.from_scipy_sparse_array(
        sparse, create_using=fnx.DiGraph()
    )
    sparse_expected = nx.from_scipy_sparse_array(
        sparse, create_using=nx.DiGraph()
    )

    _expect(
        module.from_scipy_sparse_array is fnx.from_scipy_sparse_array,
        "convert_matrix.from_scipy_sparse_array must route through fnx",
    )
    _expect(
        isinstance(sparse_actual, fnx.DiGraph),
        "convert_matrix.from_scipy_sparse_array must return an fnx DiGraph",
    )
    _expect(
        list(sparse_actual.edges(data=True))
        == list(sparse_expected.edges(data=True)),
        "convert_matrix.from_scipy_sparse_array edge data must match networkx",
    )


def test_relabel_module_graph_returning_calls_preserve_fnx_type(monkeypatch):
    module = importlib.import_module("franken_networkx.relabel")

    mapping = {0: "a", 1: "b", 2: "c", 3: "d"}
    relabeled = module.relabel_nodes(fnx.path_graph(4), mapping)
    expected_relabel = nx.relabel_nodes(nx.path_graph(4), mapping)

    _expect(isinstance(relabeled, fnx.Graph), "relabel_nodes must return an fnx Graph")
    _expect(
        sorted(relabeled.nodes()) == sorted(expected_relabel.nodes()),
        "relabel_nodes nodes must match networkx",
    )
    _expect(
        _canonical_edges(relabeled) == _canonical_edges(expected_relabel),
        "relabel_nodes edges must match networkx",
    )

    converted = module.convert_node_labels_to_integers(
        fnx.path_graph(["x", "y", "z"]),
        first_label=7,
        label_attribute="old",
    )
    expected_convert = nx.convert_node_labels_to_integers(
        nx.path_graph(["x", "y", "z"]),
        first_label=7,
        label_attribute="old",
    )

    _expect(
        isinstance(converted, fnx.Graph),
        "convert_node_labels_to_integers must return an fnx Graph",
    )
    _expect(
        sorted(converted.nodes()) == sorted(expected_convert.nodes()),
        "convert_node_labels_to_integers nodes must match networkx",
    )
    _expect(
        _canonical_edges(converted) == _canonical_edges(expected_convert),
        "convert_node_labels_to_integers edges must match networkx",
    )
    _expect(
        {node: converted.nodes[node]["old"] for node in converted}
        == {node: expected_convert.nodes[node]["old"] for node in expected_convert},
        "convert_node_labels_to_integers label attributes must match networkx",
    )

    sentinel = object()
    source = fnx.path_graph(2)

    def fake_relabel_nodes(graph, actual_mapping, copy=True, *, backend=None, **kwargs):
        _expect(graph is source, "relabel_nodes must forward the original graph")
        _expect(actual_mapping == mapping, "relabel_nodes must forward mapping")
        _expect(not copy, "relabel_nodes must forward copy")
        _expect(backend == "sentinel", "relabel_nodes must forward backend")
        _expect(kwargs == {"strict": True}, "relabel_nodes must forward backend kwargs")
        return sentinel

    def fake_convert_node_labels_to_integers(
        graph,
        first_label=0,
        ordering="default",
        label_attribute=None,
        *,
        backend=None,
        **kwargs,
    ):
        _expect(graph is source, "convert_node_labels_to_integers must forward graph")
        _expect(first_label == 5, "convert_node_labels_to_integers must forward first_label")
        _expect(ordering == "sorted", "convert_node_labels_to_integers must forward ordering")
        _expect(label_attribute == "old", "convert_node_labels_to_integers must forward label_attribute")
        _expect(backend == "sentinel", "convert_node_labels_to_integers must forward backend")
        _expect(
            kwargs == {"strict": True},
            "convert_node_labels_to_integers must forward backend kwargs",
        )
        return sentinel

    monkeypatch.setattr(fnx, "relabel_nodes", fake_relabel_nodes)
    monkeypatch.setattr(
        fnx,
        "convert_node_labels_to_integers",
        fake_convert_node_labels_to_integers,
    )
    _expect(
        module.relabel_nodes(
            source,
            mapping,
            copy=False,
            backend="sentinel",
            strict=True,
        )
        is sentinel,
        "relabel.relabel_nodes must route through fnx",
    )
    _expect(
        module.convert_node_labels_to_integers(
            source,
            first_label=5,
            ordering="sorted",
            label_attribute="old",
            backend="sentinel",
            strict=True,
        )
        is sentinel,
        "relabel.convert_node_labels_to_integers must route through fnx",
    )


def test_aliases_against_nx_for_classlike_names():
    """For the nx-only classes / converters that pure fnx doesn't
    re-implement, each must alias the same nx object so isinstance
    checks across both libraries match."""
    import networkx.utils
    import networkx.linalg
    # GraphIterator-ish names (sample from nx.utils)
    for name in ("UnionFind", "PythonRandomInterface", "decorators"):
        if hasattr(nx.utils, name):
            _expect(getattr(fnx.utils, name) is getattr(nx.utils, name), (
                f"fnx.utils.{name} must alias nx.utils.{name}"
            ))


def test_readwrite_submodule_paths_are_directly_importable():
    """``import franken_networkx.readwrite.<submodule>`` must mirror nx."""
    for name in READWRITE_SUBMODULES:
        fnx_mod = importlib.import_module(f"franken_networkx.readwrite.{name}")
        nx_mod = importlib.import_module(f"networkx.readwrite.{name}")
        _expect(fnx_mod is not None, f"franken_networkx.readwrite.{name} did not import")
        _expect(nx_mod is not None, f"networkx.readwrite.{name} did not import")


def test_readwrite_module_does_not_leak_stdlib_helpers():
    """``franken_networkx.readwrite`` should not expose internal imports."""
    import franken_networkx.readwrite as fnx_readwrite
    import networkx.readwrite as nx_readwrite

    helper_names = {
        "BytesIO",
        "Path",
        "StringIO",
        "ast",
        "bz2",
        "gzip",
        "re",
        "shlex",
        "warnings",
    }

    for name in helper_names:
        _expect(
            hasattr(fnx_readwrite, name) == hasattr(nx_readwrite, name),
            f"{name} hasattr visibility differs from networkx.readwrite",
        )
        _expect(
            (name in dir(fnx_readwrite)) == (name in dir(nx_readwrite)),
            f"{name} dir visibility differs from networkx.readwrite",
        )


def test_readwrite_submodules_keep_fnx_implemented_names():
    """Alias modules should still expose fnx's local readwrite wrappers."""
    import franken_networkx.readwrite as fnx_readwrite

    gml = importlib.import_module("franken_networkx.readwrite.gml")
    graph6 = importlib.import_module("franken_networkx.readwrite.graph6")
    sparse6 = importlib.import_module("franken_networkx.readwrite.sparse6")
    pajek = importlib.import_module("franken_networkx.readwrite.pajek")
    adjacency = importlib.import_module("franken_networkx.readwrite.json_graph.adjacency")
    cytoscape = importlib.import_module("franken_networkx.readwrite.json_graph.cytoscape")
    tree = importlib.import_module("franken_networkx.readwrite.json_graph.tree")

    for local, exported, label in (
        (gml.parse_gml, fnx_readwrite.parse_gml, "gml.parse_gml"),
        (graph6.to_graph6_bytes, fnx_readwrite.to_graph6_bytes, "graph6.to_graph6_bytes"),
        (sparse6.from_sparse6_bytes, fnx_readwrite.from_sparse6_bytes, "sparse6.from_sparse6_bytes"),
        (pajek.generate_pajek, fnx_readwrite.generate_pajek, "pajek.generate_pajek"),
        (adjacency.adjacency_graph, fnx_readwrite.adjacency_graph, "adjacency.adjacency_graph"),
        (cytoscape.cytoscape_graph, fnx_readwrite.cytoscape_graph, "cytoscape.cytoscape_graph"),
        (tree.tree_graph, fnx_readwrite.tree_graph, "tree.tree_graph"),
    ):
        _expect(local is exported, f"{label} must alias franken_networkx.readwrite")


def test_readwrite_json_graph_builders_return_fnx_graphs():
    """``fnx.readwrite`` JSON graph builders must preserve fnx graph types."""
    import franken_networkx.readwrite as fnx_readwrite

    adjacency_payload = nx.adjacency_data(nx.path_graph(3))
    cytoscape_payload = nx.cytoscape_data(nx.path_graph(3))
    tree_payload = nx.tree_data(
        nx.balanced_tree(2, 2, create_using=nx.DiGraph),
        root=0,
    )

    adjacency_graph = fnx_readwrite.adjacency_graph(adjacency_payload)
    cytoscape_graph = fnx_readwrite.cytoscape_graph(cytoscape_payload)
    tree_graph = fnx_readwrite.tree_graph(tree_payload)

    _expect(isinstance(adjacency_graph, fnx.Graph), "adjacency_graph must return fnx.Graph")
    _expect(isinstance(cytoscape_graph, fnx.Graph), "cytoscape_graph must return fnx.Graph")
    _expect(isinstance(tree_graph, fnx.DiGraph), "tree_graph must return fnx.DiGraph")


def test_readwrite_json_graph_builder_signatures_match_networkx():
    """JSON graph builders should keep nx's backend keyword surface."""
    import inspect
    import franken_networkx.readwrite as fnx_readwrite
    import networkx.readwrite as nx_readwrite

    for name in (
        "adjacency_graph",
        "cytoscape_graph",
        "node_link_graph",
        "tree_graph",
    ):
        fnx_signature = str(inspect.signature(getattr(fnx_readwrite, name)))
        nx_signature = str(inspect.signature(getattr(nx_readwrite, name)))
        _expect(
            fnx_signature in (nx_signature,),
            f"{name} signature {fnx_signature} != {nx_signature}",
        )


def test_readwrite_json_graph_builders_accept_backend_keyword():
    """NetworkX backend kwargs should validate like other readwrite wrappers."""
    import franken_networkx.readwrite as fnx_readwrite

    adjacency_payload = nx.adjacency_data(nx.path_graph(3))
    cytoscape_payload = nx.cytoscape_data(nx.path_graph(3))
    node_link_payload = nx.node_link_data(nx.path_graph(3))
    tree_payload = nx.tree_data(
        nx.balanced_tree(2, 2, create_using=nx.DiGraph),
        root=0,
    )

    for graph, expected_type, label in (
        (
            fnx_readwrite.adjacency_graph(adjacency_payload, backend="networkx"),
            fnx.Graph,
            "adjacency_graph",
        ),
        (
            fnx_readwrite.cytoscape_graph(cytoscape_payload, backend="networkx"),
            fnx.Graph,
            "cytoscape_graph",
        ),
        (
            fnx_readwrite.node_link_graph(node_link_payload, backend="networkx"),
            fnx.Graph,
            "node_link_graph",
        ),
        (
            fnx_readwrite.tree_graph(tree_payload, backend="networkx"),
            fnx.DiGraph,
            "tree_graph",
        ),
    ):
        _expect(isinstance(graph, expected_type), f"{label} returned wrong graph type")

    with pytest.raises(ImportError):
        fnx_readwrite.adjacency_graph(adjacency_payload, backend="missing")
    with pytest.raises(TypeError):
        fnx_readwrite.tree_graph(tree_payload, backend_kwargs={"x": 1})
