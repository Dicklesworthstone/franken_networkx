"""Parity for negative_edge_cycle non-string weight argument.

Bead br-r37-c1-f0i2s.

The Rust binding exposed by ``_raw_negative_edge_cycle`` declares
``weight: str`` so passing ``weight=5`` (or ``None``, or any other
non-string) raises::

    TypeError: argument 'weight': 'int' object is not an instance of 'str'

…before the algorithm runs.  nx accepts any hashable as ``weight``
(it's used as an attribute key on edge-data dicts; non-string keys
silently fall back to the unweighted-default-of-1).

This is the same drift class as br-r37-c1-blu7u (which patched
the central dijkstra / bellman_ford / floyd_warshall / astar
delegation gates) — but ``negative_edge_cycle`` has its own gate
``_should_delegate_negative_edge_cycle_to_networkx`` that was
missed in that round.
"""

from __future__ import annotations

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")

NONSTRING_WEIGHTS = [
    pytest.param(5, id="int"),
    pytest.param(1.5, id="float"),
    pytest.param(b"weight", id="bytes"),
    pytest.param(("w",), id="tuple"),
    pytest.param(None, id="None"),
]


@needs_nx
@pytest.mark.parametrize("w", NONSTRING_WEIGHTS)
def test_negative_edge_cycle_undirected_nonstring_weight_matches_nx(w):
    """Undirected path: gate now routes non-string weight to nx;
    no negative cycle is found because nx falls back to default-1
    weights and the graph has positive edges."""
    G = fnx.Graph()
    G.add_weighted_edges_from([(0, 1, -1), (1, 2, 1)])
    GX = nx.Graph()
    GX.add_weighted_edges_from([(0, 1, -1), (1, 2, 1)])
    assert fnx.negative_edge_cycle(G, weight=w) == nx.negative_edge_cycle(GX, weight=w)


@needs_nx
@pytest.mark.parametrize("w", NONSTRING_WEIGHTS)
def test_negative_edge_cycle_directed_nonstring_weight_matches_nx(w):
    """Directed path: same — non-string weight delegates to nx."""
    DG = fnx.DiGraph()
    DG.add_weighted_edges_from([(0, 1, -1), (1, 2, -1), (2, 0, -1)])
    DGX = nx.DiGraph()
    DGX.add_weighted_edges_from([(0, 1, -1), (1, 2, -1), (2, 0, -1)])
    assert fnx.negative_edge_cycle(DG, weight=w) == nx.negative_edge_cycle(DGX, weight=w)


# ---------------------------------------------------------------------------
# Regressions — string and callable weights unchanged
# ---------------------------------------------------------------------------

@needs_nx
def test_negative_edge_cycle_string_weight_unchanged():
    G = fnx.Graph()
    G.add_weighted_edges_from([(0, 1, -1), (1, 2, 1)])
    GX = nx.Graph()
    GX.add_weighted_edges_from([(0, 1, -1), (1, 2, 1)])
    assert fnx.negative_edge_cycle(G, weight="weight") == nx.negative_edge_cycle(GX, weight="weight")


@needs_nx
def test_negative_edge_cycle_callable_weight_unchanged():
    G = fnx.Graph()
    G.add_weighted_edges_from([(0, 1, -1), (1, 2, 1)])
    GX = nx.Graph()
    GX.add_weighted_edges_from([(0, 1, -1), (1, 2, 1)])
    f = fnx.negative_edge_cycle(G, weight=lambda u, v, d: d.get("weight", 1.0))
    n = nx.negative_edge_cycle(GX, weight=lambda u, v, d: d.get("weight", 1.0))
    assert f == n


@needs_nx
def test_negative_edge_cycle_real_cycle_undirected_unchanged():
    """Sanity: real undirected negative-cycle graph still detected."""
    G = fnx.Graph()
    G.add_weighted_edges_from([(0, 1, -1), (1, 2, -1), (0, 2, -1)])
    GX = nx.Graph()
    GX.add_weighted_edges_from([(0, 1, -1), (1, 2, -1), (0, 2, -1)])
    assert fnx.negative_edge_cycle(G, weight="weight") == nx.negative_edge_cycle(GX, weight="weight")


@needs_nx
@pytest.mark.parametrize("cls", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("sign", ["positive", "negative"])
@pytest.mark.parametrize("weight", ["weight", "callable"])
def test_negative_edge_cycle_answers_on_every_class(cls, sign, weight):
    """The undirected branch fed the multigraph weight function one parallel
    edge's attr dict instead of G[u][v]'s keydict, so an undirected MultiGraph
    raised AttributeError ('float' object has no attribute 'get')."""
    last = -4.0 if sign == "negative" else 4.0
    edges = [(0, 1, 1.5), (1, 2, 2.0), (2, 0, 3.0), (2, 3, last)]
    outcomes = {}
    for name, lib in (("nx", nx), ("fnx", fnx)):
        graph = getattr(lib, cls)()
        graph.add_weighted_edges_from(edges)
        if weight == "callable":
            # nx passes G[u][v]: the keydict on a multigraph. .get(..., 1) as
            # nx's own weight functions do - its helper edges carry no weight.
            if graph.is_multigraph():
                arg = lambda u, v, d: min(attrs.get("weight", 1) for attrs in d.values())  # noqa: E731
            else:
                arg = lambda u, v, d: d.get("weight", 1)  # noqa: E731
        else:
            arg = weight
        try:
            outcomes[name] = ("ok", lib.negative_edge_cycle(graph, weight=arg))
        except Exception as exc:  # noqa: BLE001 - the raise is the defect
            outcomes[name] = ("raise", type(exc).__name__)
    assert outcomes["fnx"] == outcomes["nx"]


# The native search (simple Graph / DiGraph, string weight, numbers the f64
# search adds exactly) against networkx on random graphs: the answer is a
# bool, so it must agree whatever detector found it. The directed graphs used
# to run an in-process SPFA without networkx's early exit (0.12x networkx).
def _random_twins(seed):
    import random

    r = random.Random(seed)
    n = r.choice((5, 12, 40))
    directed = seed % 3 != 0
    kind = r.choice(["int", "float", "mixed", "missing", "mostly_positive"])

    def weight():
        if kind == "int":
            return r.randint(-3, 9)
        if kind == "float":
            return r.choice([-1.5, 0.5, 2.25, 4.0, -0.25])
        if kind == "mixed":
            return r.choice([-1, 2.5, 3, -0.5])
        if kind == "missing":
            return None if r.random() < 0.5 else r.randint(-1, 5)
        return r.randint(-1, 20)

    edges = []
    for _ in range(r.choice((n, 2 * n, 4 * n))):
        w = weight()
        edges.append((r.randrange(n), r.randrange(n), {} if w is None else {"weight": w}))
    graphs = []
    for lib in (fnx, nx):
        g = (lib.DiGraph if directed else lib.Graph)()
        g.add_nodes_from(range(n))
        g.add_edges_from(edges)
        graphs.append(g)
    return graphs


@pytest.mark.parametrize("seed", range(120))
def test_negative_edge_cycle_matches_networkx_on_random_graphs(seed):
    fg, ng = _random_twins(seed)
    assert fnx.negative_edge_cycle(fg) == nx.negative_edge_cycle(ng)


@pytest.mark.parametrize(
    "value",
    [float("nan"), float("inf"), float("-inf"), "-3", 2**60, -(2**60), -(2**70)],
)
def test_weights_the_native_search_cannot_add_keep_networkx_answer(value):
    edges = [(0, 1, {"weight": 1}), (1, 2, {"weight": value}), (2, 0, {"weight": 1})]
    for directed in (True, False):
        fg = (fnx.DiGraph if directed else fnx.Graph)(edges)
        ng = (nx.DiGraph if directed else nx.Graph)(edges)
        try:
            want = ("ok", nx.negative_edge_cycle(ng))
        except Exception as exc:  # noqa: BLE001 - the exception type is the answer
            want = ("raise", type(exc).__name__)
        try:
            got = ("ok", fnx.negative_edge_cycle(fg))
        except Exception as exc:  # noqa: BLE001
            got = ("raise", type(exc).__name__)
        assert got == want, (directed, value)


@pytest.mark.parametrize("kind", ["Fraction", "Decimal"])
def test_an_exact_zero_cycle_f64_would_round_negative_keeps_networkx_answer(kind):
    # 3/10 - 1/10 - 2/10 is exactly 0, so networkx finds no negative cycle; added
    # as f64 the same cycle comes out at about -2.8e-17. The native search adds
    # in f64, so these weights must stay on the exact route.
    from decimal import Decimal
    from fractions import Fraction

    exact = Fraction if kind == "Fraction" else (lambda p, q: Decimal(p) / Decimal(q))
    edges = [
        (0, 1, {"weight": exact(3, 10)}),
        (1, 2, {"weight": exact(-1, 10)}),
        (2, 0, {"weight": exact(-2, 10)}),
    ]
    fg, ng = fnx.DiGraph(edges), nx.DiGraph(edges)
    assert fnx.negative_edge_cycle(fg) == nx.negative_edge_cycle(ng)


def test_the_directed_answer_comes_from_the_native_search(monkeypatch):
    # A planted fault in the native route must show: the tests above reach it.
    import franken_networkx as package

    fg = fnx.DiGraph([(0, 1, {"weight": -2}), (1, 0, {"weight": 1})])
    monkeypatch.setattr(package, "_raw_negative_edge_cycle", lambda G, weight: "native")
    assert fnx.negative_edge_cycle(fg) == "native"


@needs_nx
@pytest.mark.parametrize("cls", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("heuristic", [True, False])
@pytest.mark.parametrize("callable_weight", [False, True])
def test_overflowing_negative_cycle_preserves_heuristic(
    cls, heuristic, callable_weight
):
    # The count-only detector saturates to -inf before it visits a node n times.
    # NX's default heuristic finds the repeated update first; disabling that
    # heuristic deliberately retains NX's different floating-point answer.
    twins = []
    for lib in (fnx, nx):
        graph = getattr(lib, cls)()
        graph.add_nodes_from(range(12))
        graph.add_edge(0, 1, weight=-1e308)
        if graph.is_directed():
            graph.add_edge(1, 0, weight=1)
        twins.append(graph)

    weight = "weight"
    if callable_weight:
        if twins[0].is_multigraph():
            weight = lambda u, v, data: min(
                attrs.get("weight", 1) for attrs in data.values()
            )
        else:
            weight = lambda u, v, data: data.get("weight", 1)

    want = nx.negative_edge_cycle(twins[1], weight=weight, heuristic=heuristic)
    assert want is heuristic
    assert fnx.negative_edge_cycle(
        twins[0], weight=weight, heuristic=heuristic
    ) is want


@needs_nx
@pytest.mark.parametrize("cls", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("heuristic", [True, False])
def test_callable_sees_temporary_source_edges(cls, heuristic):
    # The source edges carry empty attrs in NX, so callbacks that require an
    # attribute must raise even when every original edge has that attribute.
    twins = [getattr(lib, cls)([(0, 1, {"cost": 2})]) for lib in (fnx, nx)]
    if twins[0].is_multigraph():
        weight = lambda u, v, data: min(
            attrs["cost"] for attrs in data.values()
        )
    else:
        weight = lambda u, v, data: data["cost"]

    for lib, graph in zip((fnx, nx), twins):
        with pytest.raises(KeyError, match="cost"):
            lib.negative_edge_cycle(graph, weight=weight, heuristic=heuristic)
        assert list(graph) == [0, 1]
        assert graph.number_of_edges() == 1


@needs_nx
@pytest.mark.parametrize("cls", ["MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("heuristic", [True, False])
def test_callable_selfloop_uses_each_parallel_edge_keydict(cls, heuristic):
    twins = []
    for lib in (fnx, nx):
        graph = getattr(lib, cls)()
        graph.add_edge(0, 0, key="positive", cost=2)
        graph.add_edge(0, 0, key="negative", cost=-3)
        twins.append(graph)

    weight = lambda u, v, data: min(
        attrs.get("cost", 1) for attrs in data.values()
    )
    assert nx.negative_edge_cycle(
        twins[1], weight=weight, heuristic=heuristic
    ) is True
    assert fnx.negative_edge_cycle(
        twins[0], weight=weight, heuristic=heuristic
    ) is True


def test_disabled_heuristic_uses_its_matching_relaxation_loop(monkeypatch):
    import franken_networkx as package

    graph = fnx.DiGraph([
        (0, 1, {"weight": -2}),
        (1, 0, {"weight": 1}),
    ])
    monkeypatch.setattr(
        package, "_raw_negative_edge_cycle", lambda G, weight: "native"
    )
    assert fnx.negative_edge_cycle(graph, heuristic=False) is True


@needs_nx
@pytest.mark.parametrize("cls", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("selfloop", [False, True])
def test_virtual_source_rounding_distinguishes_tiny_negative_selfloops(cls, selfloop):
    twins = []
    for lib in (fnx, nx):
        graph = getattr(lib, cls)()
        graph.add_node("removed")
        graph.add_nodes_from([0, 1, 2])
        graph.remove_node("removed")
        graph.add_edge(0, 0 if selfloop else 1, weight=-1e-300)
        twins.append(graph)

    # The ordinary edge cannot improve the virtual-source seed of 1.
    # Negative self-loops are checked explicitly before relaxation.
    want = nx.negative_edge_cycle(twins[1])
    assert want is selfloop
    assert fnx.negative_edge_cycle(twins[0]) is want


@needs_nx
@pytest.mark.parametrize("cls", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("heuristic", [True, False])
@pytest.mark.parametrize("entrypoint", ["native", "foreign", "backend", "warm-backend"])
def test_negative_cycle_callback_observes_live_topology(
    cls, heuristic, entrypoint, monkeypatch
):
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)

    def run(module, algorithm, warm=False):
        graph = getattr(module, cls)()
        graph.add_nodes_from([-1, -2, ("isolated", 7)])
        graph.add_weighted_edges_from([(0, 1, 1), (1, 2, 1)])
        if warm:
            nx.relabel_nodes(graph, {}, backend="franken_networkx")
            assert graph.__networkx_cache__["backends"]["franken_networkx"]
        trace = []
        changed = False

        def weight(u, v, data):
            nonlocal changed
            trace.append((u, v, -3 in graph))
            if u == -3 and not changed:
                # This creates a new adjacency entry, not just a changed
                # weight in an already snapshotted edge dictionary.
                graph.add_edge(2, 0, weight=-4)
                changed = True
            if graph.is_multigraph():
                return min(attrs.get("weight", 1) for attrs in data.values())
            return data.get("weight", 1)

        result = algorithm(graph, weight=weight, heuristic=heuristic)
        assert changed
        assert -3 not in graph
        assert -1 in graph and -2 in graph and ("isolated", 7) in graph
        assert graph.has_edge(2, 0), "cleanup discarded the callback's edit"
        return result, trace, list(graph), list(graph.edges(data=True))

    expected = run(nx, nx.negative_edge_cycle)
    assert expected[0] is True
    assert all(source_visible for _, _, source_visible in expected[1])
    if entrypoint in {"backend", "warm-backend"}:
        def algorithm(graph, **kwargs):
            return nx.negative_edge_cycle(
                graph, backend="franken_networkx", **kwargs
            )
    else:
        algorithm = fnx.negative_edge_cycle
    module = fnx if entrypoint == "native" else nx
    assert run(module, algorithm, warm=entrypoint == "warm-backend") == expected


@needs_nx
@pytest.mark.parametrize("cls", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("heuristic", [True, False])
@pytest.mark.parametrize("kind", ["frozen", "view"])
@pytest.mark.parametrize("has_edges", [False, True])
def test_negative_cycle_respects_read_only_graphs(cls, heuristic, kind, has_edges):
    for module in (fnx, nx):
        graph = getattr(module, cls)()
        graph.add_nodes_from([0, 1])
        if has_edges:
            graph.add_edge(0, 1, weight=-2)
        graph = module.freeze(graph) if kind == "frozen" else graph.subgraph([0, 1])
        if has_edges:
            with pytest.raises(nx.NetworkXError, match="Frozen graph can't be modified"):
                module.negative_edge_cycle(graph, heuristic=heuristic)
        else:
            assert module.negative_edge_cycle(graph, heuristic=heuristic) is False
        assert list(graph) == [0, 1]


@needs_nx
@pytest.mark.parametrize("cls", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("phase", ["selfloop", "source", "relaxation"])
@pytest.mark.parametrize("error", [ValueError, nx.NetworkXUnbounded])
def test_negative_cycle_cleans_up_source_after_callback_errors(cls, phase, error):
    def run(module):
        graph = getattr(module, cls)()
        graph.add_weighted_edges_from([(0, 1, 2), (1, 2, 2)])
        if phase == "selfloop":
            graph.add_edge(0, 0, weight=1)
        before = list(graph), list(graph.edges(data=True))
        trace = []

        def weight(u, v, data):
            trace.append((u, v, -1 in graph))
            fail = (
                (phase == "selfloop" and u == v)
                or (phase == "source" and u == -1)
                or (phase == "relaxation" and u >= 0)
            )
            if fail:
                raise error("weight callback failed")
            if graph.is_multigraph():
                return min(attrs.get("weight", 1) for attrs in data.values())
            return data.get("weight", 1)

        try:
            outcome = ("result", module.negative_edge_cycle(graph, weight=weight))
        except ValueError as exc:
            outcome = (type(exc).__name__, str(exc))
        assert (list(graph), list(graph.edges(data=True))) == before
        assert -1 not in graph
        return outcome, trace

    assert run(fnx) == run(nx)


@needs_nx
@pytest.mark.parametrize("cls", ["Graph", "DiGraph"])
def test_negative_cycle_preserves_instance_graph_protocol_overrides(cls):
    for module in (fnx, nx):
        graph = getattr(module, cls)([(0, 1, {"weight": -2})])
        # The initial size check wins even over a forbidden insertion.
        graph.size = lambda: 0
        graph.add_edges_from = lambda edges: pytest.fail("unexpected insertion")
        assert module.negative_edge_cycle(graph) is False

        del graph.size
        seen = []
        original_add = getattr(module, cls).add_edges_from
        original_remove = getattr(module, cls).remove_node

        def add(edges):
            seen.append(("add", list(edges)))
            return original_add(graph, seen[-1][1])

        def remove(node):
            seen.append(("remove", node))
            return original_remove(graph, node)

        graph.add_edges_from = add
        graph.remove_node = remove
        module.negative_edge_cycle(graph)
        assert seen == [("add", [(-1, 0), (-1, 1)]), ("remove", -1)]


@needs_nx
@pytest.mark.parametrize("cls", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_negative_cycle_evaluates_heuristic_after_source_insertion(cls):
    traces = []
    for module in (fnx, nx):
        graph = getattr(module, cls)([(0, 1)])
        seen = []

        class Heuristic:
            def __bool__(self):
                seen.append(-1 in graph)
                return True

        assert module.negative_edge_cycle(graph, heuristic=Heuristic()) is False
        assert -1 not in graph
        traces.append(seen)
    assert traces[0] == traces[1]
    assert traces[0] and all(traces[0])
