"""greedy_color on DIRECTED graphs goes through a structural nx.DiGraph copy.

br-r37-c1-vevfq. greedy_color has two fast paths and both were gated on
``not G.is_directed()``, so directed graphs paid the FAITHFUL fnx->nx conversion and
measured 0.136x against networkx (19,304,753 against 2,624,760 Ir/call on a 250-node
DiGraph) while the SAME function on an undirected graph is a win. The structural shortcut
was excluded from directed on the grounds that it "would drop parallel edges / direction",
which is true of an ``nx.Graph`` copy but not of an ``nx.DiGraph`` one.

greedy_color is structure-only - no node or edge attribute affects the colouring - so the
structural copy must be byte-identical to the faithful conversion. These cases pin that,
across the axes that can break it:

  * every string strategy, including the connected_sequential family, which is
    order-sensitive (br-r37-c1-rqsur) and which raises NetworkXNotImplemented on a
    directed graph - the raise has to survive too, so exceptions are compared by type AND
    args rather than by type alone;
  * PERMUTED node insertion order, since a structural copy rebuilds adjacency in
    node-major edge order rather than the parent's adj-insertion order;
  * graphs carrying node and edge attributes, which the structural copy drops and the
    faithful conversion keeps - the colouring must not notice.

This change did NOT make the row a win: it is 1.61x self and lands at 0.219x. Closing it
needs a native directed kernel, the way the undirected class already has one. The point of
this file is that the shortcut is behaviour-neutral, so that work can proceed on top of it.
"""

import random

import networkx as nx
import pytest

import franken_networkx as fnx

# random_sequential is deliberately absent: it shuffles, so it cannot be compared
# across two graph objects.
STRATEGIES = [
    "largest_first",
    "smallest_last",
    "independent_set",
    "connected_sequential",
    "connected_sequential_bfs",
    "connected_sequential_dfs",
    "saturation_largest_first",
    "DSATUR",
]


def _outcome(fn):
    try:
        value = fn()
    except Exception as exc:  # noqa: BLE001 - the exception IS the observation
        return ("raise", type(exc).__name__, tuple(str(a) for a in exc.args))
    return ("ok", {str(k): v for k, v in value.items()})


def _build(module, n, seed, permute, attributed):
    rng = random.Random(seed)
    graph = module.DiGraph()
    labels = list(range(n))
    if permute:
        rng.shuffle(labels)
    graph.add_nodes_from(labels)
    for i in range(n):
        for _ in range(3):
            j = rng.randrange(n)
            if i != j:
                if attributed:
                    graph.add_edge(labels[i], labels[j], weight=float(rng.randint(1, 5)))
                else:
                    graph.add_edge(labels[i], labels[j])
    if attributed:
        for node in graph.nodes():
            graph.nodes[node]["color"] = "r"
    return graph


@pytest.mark.parametrize("strategy", STRATEGIES)
@pytest.mark.parametrize("permute", [False, True])
@pytest.mark.parametrize("attributed", [False, True])
@pytest.mark.parametrize("seed", range(6))
def test_directed_greedy_color_matches_networkx(strategy, permute, attributed, seed):
    n = random.Random(seed).randint(6, 30)
    fnx_graph = _build(fnx, n, seed, permute, attributed)
    nx_graph = _build(nx, n, seed, permute, attributed)
    assert _outcome(lambda: fnx.greedy_color(fnx_graph, strategy=strategy)) == _outcome(
        lambda: nx.greedy_color(nx_graph, strategy=strategy)
    )


def test_directed_multigraph_keeps_the_faithful_path():
    """A structural copy WOULD drop parallel edges, so multigraphs stay excluded."""
    fg, ng = fnx.MultiDiGraph(), nx.MultiDiGraph()
    for graph in (fg, ng):
        graph.add_edges_from([(0, 1), (0, 1), (1, 2), (2, 0)])
    assert _outcome(lambda: fnx.greedy_color(fg)) == _outcome(lambda: nx.greedy_color(ng))
