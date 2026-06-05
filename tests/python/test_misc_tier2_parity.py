import inspect

import networkx as nx
import pytest

import franken_networkx as fnx


def normalize_cycles(cycles):
    return sorted(sorted(cycle) for cycle in cycles)


def minimum_cycle_basis_port_case(case):
    graph = fnx.Graph()
    expected = nx.Graph()

    for node in case.get("nodes", ()):
        graph.add_node(node)
        expected.add_node(node)

    for edge in case["edges"]:
        if len(edge) == 2:
            u, v = edge
            attrs = {}
        else:
            u, v, attrs = edge
        graph.add_edge(u, v, **attrs)
        expected.add_edge(u, v, **attrs)

    return graph, expected, case.get("weight")


MINIMUM_CYCLE_BASIS_PORT_CASES = [
    pytest.param(
        {"nodes": [], "edges": []},
        id="empty",
    ),
    pytest.param(
        {"edges": [(0, 1), (1, 2), (2, 3)]},
        id="tree",
    ),
    pytest.param(
        {"edges": [(0, 1), (1, 2), (2, 0)]},
        id="triangle",
    ),
    pytest.param(
        {"edges": [(2, 1), (1, 0), (0, 2)]},
        id="reverse-insertion-triangle",
    ),
    pytest.param(
        {
            "edges": [(0, 1), (1, 2), (2, 3), (3, 0), (0, 2), (1, 3)],
        },
        id="complete-graph-k4",
    ),
    pytest.param(
        {
            "edges": [("a", "b"), ("b", "c"), ("c", "a"), ("c", "d"), ("d", "e"), ("e", "c")],
        },
        id="two-triangles-sharing-node",
    ),
    pytest.param(
        {
            "edges": [(0, 1), (1, 2), (2, 3), (3, 0), (1, 4), (4, 5), (5, 2)],
        },
        id="two-squares-sharing-path",
    ),
    pytest.param(
        {
            "edges": [
                ("a", "b", {"weight": 1}),
                ("b", "c", {"weight": 1}),
                ("c", "d", {"weight": 1}),
                ("d", "a", {"weight": 1}),
                ("a", "c", {"weight": 2}),
            ],
            "weight": "weight",
        },
        id="weighted-square-diagonal",
    ),
    pytest.param(
        {
            "nodes": ["iso"],
            "edges": [(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 2)],
        },
        id="disconnected-components-and-isolate",
    ),
    pytest.param(
        {
            "edges": [
                ("a", "b", {"weight": 7}),
                ("b", "c"),
                ("c", "a", {"weight": 2}),
            ],
            "weight": "weight",
        },
        id="missing-weight-defaults-to-one",
    ),
    pytest.param(
        {
            "edges": [
                ("a", "b", {"cost": 1.5}),
                ("b", "c", {"cost": 2.5}),
                ("c", "a", {"cost": 0.5}),
                ("c", "d", {"cost": 9.0}),
                ("d", "e", {"cost": 1.0}),
                ("e", "c", {"cost": 1.0}),
            ],
            "weight": "cost",
        },
        id="weighted-float-cost-attribute",
    ),
    pytest.param(
        {"edges": [("loop", "loop")]},
        id="self-loop",
    ),
]


def test_minimum_cycle_basis_signature_inventory_matches_networkx():
    nx_signature = inspect.signature(nx.minimum_cycle_basis)
    fnx_signature = inspect.signature(fnx.minimum_cycle_basis)

    # br-r37-c1-mcbsig-update: cycle 178 (and earlier signature-parity
    # work) added the canonical ``*, backend=None, **backend_kwargs``
    # dispatch surface to fnx wrappers so ``nx.minimum_cycle_basis(G,
    # backend='networkx')`` works on fnx.  Compare the core
    # user-facing params after stripping the dispatch-surface kwargs
    # — fnx and nx must agree on both core and dispatch params.
    def _strip_dispatch(params):
        return [k for k in params if k not in ("backend", "backend_kwargs")]

    fnx_core = _strip_dispatch(fnx_signature.parameters)
    nx_core = _strip_dispatch(nx_signature.parameters)
    assert fnx_core == nx_core == ["G", "weight"]
    assert fnx_signature.parameters["weight"].default is None
    assert nx_signature.parameters["G"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert nx_signature.parameters["weight"].default is None
    # Also assert the full signature including dispatch surface matches nx
    assert str(fnx_signature) == str(nx_signature)


def test_chordless_cycles_returns_iterator_and_matches_networkx():
    graph = fnx.cycle_graph(4)
    expected = nx.cycle_graph(4)

    cycles = fnx.chordless_cycles(graph)

    assert iter(cycles) is cycles
    assert normalize_cycles(cycles) == normalize_cycles(nx.chordless_cycles(expected))


def test_chordless_cycles_preserve_networkx_order():
    graph = fnx.Graph()
    expected = nx.Graph()

    edges = [
        ("d", "a"),
        ("a", "c"),
        ("c", "d"),
        ("a", "b"),
        ("b", "c"),
        ("c", "a"),
    ]
    graph.add_edges_from(edges)
    expected.add_edges_from(edges)

    assert list(fnx.chordless_cycles(graph)) == list(nx.chordless_cycles(expected))


def test_chromatic_polynomial_matches_networkx_expression():
    graph = fnx.complete_graph(4)
    expected = nx.complete_graph(4)

    try:
        import sympy  # noqa: F401
    except ModuleNotFoundError:
        try:
            nx.chromatic_polynomial(expected)
        except ModuleNotFoundError as exc:
            with pytest.raises(ModuleNotFoundError, match=str(exc)):
                fnx.chromatic_polynomial(graph)
        else:
            pytest.fail("expected NetworkX chromatic_polynomial to require sympy")
    else:
        assert str(fnx.chromatic_polynomial(graph)) == str(nx.chromatic_polynomial(expected))


def test_minimum_cycle_basis_matches_networkx_on_triangle():
    graph = fnx.Graph()
    graph.add_edges_from([(0, 1), (1, 2), (2, 0)])
    expected = nx.Graph()
    expected.add_edges_from([(0, 1), (1, 2), (2, 0)])

    assert normalize_cycles(fnx.minimum_cycle_basis(graph)) == normalize_cycles(
        nx.minimum_cycle_basis(expected)
    )


def test_minimum_cycle_basis_order_parity_under_adversarial_hash_seed():
    # br-r37-c1-cux5q: nx's basis ORDER comes from CPython set iteration
    # (`chords = G.edges - tree_edges - ...`), so it varies with
    # PYTHONHASHSEED. The Rust kernel's deterministic order diverged under
    # PYTHONHASHSEED=2 (two-triangles fixture). That order is tied to
    # CPython's set implementation, so the public parity path uses the
    # in-process nx reference per component until a native compatible
    # primitive exists. Pin exact (order-sensitive) equality under a few
    # seeds via subprocesses, including the seed that caught the divergence.
    import subprocess
    import sys

    code = (
        "import networkx as nx, franken_networkx as fnx\n"
        "def b(mod):\n"
        "    g = mod.Graph()\n"
        "    for e in [('a','b'),('b','c'),('c','a'),('c','d'),('d','e'),('e','c')]:\n"
        "        g.add_edge(*e)\n"
        "    return g\n"
        "assert fnx.minimum_cycle_basis(b(fnx)) == nx.minimum_cycle_basis(b(nx))\n"
    )
    for seed in ("0", "1", "2", "42"):
        proc = subprocess.run(
            [sys.executable, "-c", code],
            env={
                **__import__("os").environ,
                "PYTHONHASHSEED": seed,
            },
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert proc.returncode == 0, f"seed {seed}: {proc.stderr[-500:]}"


def test_minimum_cycle_basis_weighted_cycle_set_matches_networkx():
    graph = fnx.Graph()
    expected = nx.Graph()

    for u, v, weight in [
        ("a", "b", 1),
        ("b", "c", 1),
        ("c", "d", 1),
        ("d", "a", 1),
        ("a", "c", 2),
    ]:
        graph.add_edge(u, v, weight=weight)
        expected.add_edge(u, v, weight=weight)

    assert normalize_cycles(fnx.minimum_cycle_basis(graph, weight="weight")) == normalize_cycles(
        nx.minimum_cycle_basis(expected, weight="weight")
    )


@pytest.mark.parametrize("case", MINIMUM_CYCLE_BASIS_PORT_CASES)
def test_minimum_cycle_basis_port_fixture_matrix_matches_networkx(case):
    graph, expected, weight = minimum_cycle_basis_port_case(case)
    actual_basis = fnx.minimum_cycle_basis(graph, weight=weight)
    expected_basis = nx.minimum_cycle_basis(expected, weight=weight)

    assert actual_basis == expected_basis


def test_minimum_cycle_basis_graph_family_rejections_match_networkx():
    digraph = fnx.DiGraph()
    digraph.add_edge(0, 1)
    multigraph = fnx.MultiGraph()
    multigraph.add_edge(0, 1)

    with pytest.raises(fnx.NetworkXNotImplemented, match="not implemented for directed type"):
        fnx.minimum_cycle_basis(digraph)
    with pytest.raises(nx.NetworkXNotImplemented, match="not implemented for directed type"):
        nx.minimum_cycle_basis(nx.DiGraph([(0, 1)]))

    with pytest.raises(fnx.NetworkXNotImplemented, match="not implemented for multigraph type"):
        fnx.minimum_cycle_basis(multigraph)
    with pytest.raises(nx.NetworkXNotImplemented, match="not implemented for multigraph type"):
        nx.minimum_cycle_basis(nx.MultiGraph([(0, 1)]))


def test_equitable_color_matches_networkx_on_cycle():
    graph = fnx.cycle_graph(4)
    expected = nx.cycle_graph(4)

    assert fnx.equitable_color(graph, 3) == nx.equitable_color(expected, 3)


def test_equitable_color_native_avoids_networkx(monkeypatch):
    graph = fnx.cycle_graph(4)
    expected = nx.cycle_graph(4)
    expected_coloring = nx.equitable_color(expected, 3)

    monkeypatch.setattr(
        nx,
        "equitable_color",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("delegated")),
    )

    assert fnx.equitable_color(graph, 3) == expected_coloring


def test_chordless_cycles_native_avoids_networkx(monkeypatch):
    graph = fnx.complete_graph(4)
    expected = nx.complete_graph(4)
    expected_cycles = normalize_cycles(nx.chordless_cycles(expected))

    monkeypatch.setattr(
        nx,
        "chordless_cycles",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("delegated")),
    )

    assert normalize_cycles(fnx.chordless_cycles(graph)) == expected_cycles


def test_chromatic_polynomial_native_avoids_networkx(monkeypatch):
    graph = fnx.complete_graph(4)
    expected = nx.complete_graph(4)

    try:
        expected_value = str(nx.chromatic_polynomial(expected))
    except ModuleNotFoundError as exc:
        monkeypatch.setattr(
            nx,
            "chromatic_polynomial",
            lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("delegated")),
        )
        with pytest.raises(ModuleNotFoundError, match=str(exc)):
            fnx.chromatic_polynomial(graph)
    else:
        monkeypatch.setattr(
            nx,
            "chromatic_polynomial",
            lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("delegated")),
        )
        assert str(fnx.chromatic_polynomial(graph)) == expected_value
