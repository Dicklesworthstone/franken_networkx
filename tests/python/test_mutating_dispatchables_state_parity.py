"""Every input-mutating dispatchable fnx implements leaves the graph like networkx.

br-r37-c1-rc0923-epic-silent-wrong-answers-nro4w.4. NetworkX marks these
functions ``mutates_input`` in its dispatch registry. When fnx runs one, the
graph it mutates is an fnx graph (an fnx input, or the converted copy that
networkx's dispatcher hands the backend). So the contract fnx owns is: after the
call, that graph is exactly what networkx leaves on an equal networkx graph —
same nodes, edges, attribute data and iteration order — and the return value
agrees.

What this does NOT cover, by networkx's own design: an explicit
``backend="franken_networkx"`` on a networkx graph. networkx's dispatcher then
converts the input and calls the backend on the copy, logging "This may change
behavior by not mutating inputs" (networkx/utils/backends.py); no backend can
write back to the caller's graph through that path. networkx's backend-TEST
mode does copy mutations back, which is what networkx's own
``algorithms/tests/test_swap.py`` exercises.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx


def _state(G):
    if G.is_multigraph():
        edges = list(G.edges(keys=True, data=True))
    else:
        edges = list(G.edges(data=True))
    return {
        "class": (G.is_directed(), G.is_multigraph()),
        "nodes": list(G.nodes(data=True)),
        "edges": edges,
        "graph": dict(G.graph),
    }


def _undirected(module):
    G = module.Graph()
    G.add_edges_from(
        [(0, 1, {"weight": 2.0}), (1, 2, {"weight": 1.0}), (2, 3, {"weight": 4.0}),
         (3, 0, {"weight": 3.0}), (1, 3, {"weight": 5.0}), (3, 4, {"weight": 1.5})]
    )
    G.nodes[0]["lbl"] = "a"
    G.nodes[2]["lbl"] = "c"
    G.graph["name"] = "u"
    return G


def _directed(module):
    G = module.DiGraph()
    G.add_edges_from(
        [(0, 1, {"weight": 2.0}), (1, 2, {"weight": 1.0}), (2, 0, {"weight": 4.0}),
         (2, 3, {"weight": 3.0}), (3, 1, {"weight": 5.0}), (0, 3, {"weight": 1.5}),
         (3, 4, {"weight": 2.5}), (4, 0, {"weight": 0.5})]
    )
    G.graph["name"] = "d"
    return G


def _swap_graph(module, directed=False):
    base = nx.gnm_random_graph(24, 60, seed=11, directed=directed)
    G = (module.DiGraph if directed else module.Graph)()
    G.add_edges_from(base.edges())
    return G


def _connected_swap_graph(module):
    G = module.Graph()
    G.add_edges_from(nx.connected_watts_strogatz_graph(24, 4, 0.3, seed=5).edges())
    return G


# (case id, graph builder, call(module, G) -> return value)
CASES = [
    ("set_node_attributes_scalar_map", _undirected,
     lambda m, G: m.set_node_attributes(G, {0: "x", 1: "y"}, "lbl")),
    ("set_node_attributes_dict_of_dicts", _undirected,
     lambda m, G: m.set_node_attributes(G, {0: {"p": 1}, 4: {"q": 2}})),
    ("set_edge_attributes_map", _undirected,
     lambda m, G: m.set_edge_attributes(G, {(0, 1): 9.0, (3, 4): 7.0}, "weight")),
    ("set_edge_attributes_scalar", _undirected,
     lambda m, G: m.set_edge_attributes(G, 1.0, "cap")),
    ("remove_node_attributes", _undirected,
     lambda m, G: m.remove_node_attributes(G, "lbl")),
    ("remove_edge_attributes", _undirected,
     lambda m, G: m.remove_edge_attributes(G, "weight")),
    ("relabel_nodes_in_place", _undirected,
     lambda m, G: m.relabel_nodes(G, {0: "x", 4: "z"}, copy=False)),
    ("relabel_nodes_in_place_chained", _undirected,
     lambda m, G: m.relabel_nodes(G, {0: 5, 1: 0}, copy=False)),
    # A cyclic mapping cannot be applied in place: networkx raises, leaving
    # the graph as it was.
    ("relabel_nodes_in_place_cyclic_raises", _undirected,
     lambda m, G: m.relabel_nodes(G, {0: 1, 1: 0}, copy=False)),
    ("contracted_nodes_in_place", _undirected,
     lambda m, G: m.contracted_nodes(G, 0, 1, copy=False)),
    ("contracted_nodes_in_place_no_self_loops", _undirected,
     lambda m, G: m.contracted_nodes(G, 0, 1, self_loops=False, copy=False)),
    ("contracted_edge_in_place", _undirected,
     lambda m, G: m.contracted_edge(G, (1, 2), copy=False)),
    ("contracted_nodes_in_place_directed", _directed,
     lambda m, G: m.contracted_nodes(G, 0, 2, copy=False)),
    ("barycenter_stores_attr", _undirected,
     lambda m, G: m.barycenter(G, attr="bary")),
    ("incremental_closeness_centrality_insertion", _undirected,
     lambda m, G: m.incremental_closeness_centrality(G, (0, 2), insertion=True)),
    ("minimum_spanning_arborescence", _directed,
     lambda m, G: _state(m.minimum_spanning_arborescence(G))),
    ("maximum_spanning_arborescence", _directed,
     lambda m, G: _state(m.maximum_spanning_arborescence(G))),
    ("minimum_branching", _directed,
     lambda m, G: _state(m.minimum_branching(G))),
    # networkx exposes minimal_branching only under algorithms.tree.
    ("minimal_branching", _directed,
     lambda m, G: _state(m.algorithms.tree.minimal_branching(G))),
    ("recursive_simple_cycles", _directed,
     lambda m, G: m.recursive_simple_cycles(G)),
    ("double_edge_swap_seeded", _swap_graph,
     lambda m, G: m.double_edge_swap(G, nswap=6, max_tries=400, seed=3)),
    ("directed_edge_swap_seeded", lambda m: _swap_graph(m, directed=True),
     lambda m, G: m.directed_edge_swap(G, nswap=4, max_tries=400, seed=3)),
    ("connected_double_edge_swap_seeded", _connected_swap_graph,
     lambda m, G: m.connected_double_edge_swap(G, nswap=12, seed=3)),
]


@pytest.mark.parametrize("build, call", [c[1:] for c in CASES], ids=[c[0] for c in CASES])
def test_fnx_graph_is_left_exactly_like_networkx(build, call):
    gnx, gfx = build(nx), build(fnx)
    assert _state(gfx) == _state(gnx)  # identical starting points
    want = _outcome(call, nx, gnx)
    got = _outcome(call, fnx, gfx)
    assert _state(gfx) == _state(gnx)  # also the partial state after a raise
    assert got == want


def _outcome(call, module, G):
    try:
        value = call(module, G)
    except Exception as exc:  # compared by type name and message
        return ("raised", type(exc).__name__, str(exc))
    # In-place calls return the mutated graph itself: compare identity, not
    # an fnx graph against a networkx graph.
    return ("returned-self",) if value is G else ("returned", value)


def test_every_implemented_mutating_dispatchable_is_covered():
    """A new mutates_input function routed to fnx must get a row above."""
    from networkx.utils.backends import _registered_algorithms

    from franken_networkx.backend import backend_interface

    implemented = set()
    for name, dispatchable in _registered_algorithms.items():
        if not dispatchable.mutates_input:
            continue
        try:
            getattr(backend_interface, name)
        except AttributeError:
            continue
        implemented.add(name)
    covered = {case_id for case_id, _, _ in CASES}
    missing = sorted(
        name for name in implemented if not any(cid.startswith(name) for cid in covered)
    )
    assert not missing, f"mutates_input dispatchables fnx implements with no state-parity row: {missing}"
