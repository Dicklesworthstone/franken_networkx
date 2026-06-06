"""Generators matrix 2026-06-06: adjacency-row ORDER parity for classic
generators. Root cause: rust_graph_to_py_standalone rebuilt graphs from
edges_ordered() (canonical-key SORTED), scrambling rows for any kernel
whose insertion order isn't sorted (tadpole's cycle-closing edge,
sudoku's three passes) and MASKING kernels with wrong emission order
that the sort happened to fix (petersen). Now: wholesale inner clone +
nx-exact kernel emission orders.
"""

import networkx as nx
import pytest

import franken_networkx as fnx


def _rows(g):
    out = {repr(n): [repr(x) for x in g[n]] for n in g}
    if g.is_directed():
        out["__pred__"] = {repr(n): [repr(x) for x in g.pred[n]] for n in g}
    return out


GENS = [
    ("tadpole", lambda m: m.tadpole_graph(4, 3)),
    ("tadpole big", lambda m: m.tadpole_graph(7, 5)),
    ("sudoku2", lambda m: m.sudoku_graph(2)),
    ("sudoku3", lambda m: m.sudoku_graph(3)),
    ("petersen", lambda m: m.petersen_graph()),
    ("chvatal", lambda m: m.chvatal_graph()),
    ("wheel", lambda m: m.wheel_graph(7)),
    ("barbell", lambda m: m.barbell_graph(5, 3)),
    ("lollipop", lambda m: m.lollipop_graph(5, 3)),
    ("hypercube", lambda m: m.hypercube_graph(3)),
    ("mycielski", lambda m: m.mycielski_graph(4)),
    ("turan", lambda m: m.turan_graph(8, 3)),
    ("caveman", lambda m: m.caveman_graph(3, 4)),
    ("dorogovtsev", lambda m: m.dorogovtsev_goltsev_mendes_graph(2)),
]


@pytest.mark.parametrize("name,fn", GENS)
def test_generator_rows_match_nx(name, fn):
    assert _rows(fn(fnx)) == _rows(fn(nx)), name


class TestMultigraphProjectionRowOrder:
    """Generators-matrix follow-up: the MultiGraph->simple projections
    (used by every algorithm running on Multi classes via GraphRef)
    rebuilt from edges_ordered() — a u-major adjacency walk that HOISTS
    reverse-orientation cells, scrambling row order and diverging
    BFS/DFS tie-breaks from nx. Projections now restore the source's
    row orders."""

    @pytest.mark.parametrize("cls", ["MultiGraph", "MultiDiGraph"])
    def test_traversal_from_hoisted_node(self, cls):
        gn, gf = getattr(nx, cls)(), getattr(fnx, cls)()
        for g in (gn, gf):
            for e in [(0, 1), (1, 2), (2, 3), (3, 0), (3, 4)]:
                g.add_edge(*e)
        assert list(fnx.bfs_tree(gf, 3)) == list(nx.bfs_tree(gn, 3))
        assert list(fnx.dfs_preorder_nodes(gf, 3)) == list(nx.dfs_preorder_nodes(gn, 3))

    def test_random_multigraph_traversal_corpus(self):
        import random

        rnd = random.Random(7)
        for trial in range(15):
            cls = "MultiGraph" if trial % 2 else "MultiDiGraph"
            gn, gf = getattr(nx, cls)(), getattr(fnx, cls)()
            for _ in range(rnd.randrange(5, 40)):
                u, v = rnd.randrange(9), rnd.randrange(9)
                if u != v:
                    gn.add_edge(u, v)
                    gf.add_edge(u, v)
            s = next(iter(gn))
            assert list(fnx.bfs_tree(gf, s)) == list(nx.bfs_tree(gn, s)), trial
            assert list(fnx.single_source_shortest_path_length(gf, s)) == list(
                nx.single_source_shortest_path_length(gn, s)
            ), trial


def test_wheel_native_fast_path_reenabled():
    """br-r37-c1-o97vk resolved by the u-major-hoist converter fix: the
    rust wheel kernel was never wrong — native route re-enabled."""
    for n in range(0, 12):
        a = {repr(x): [repr(y) for y in fnx.wheel_graph(n)[x]] for x in fnx.wheel_graph(n)}
        b = {repr(x): [repr(y) for y in nx.wheel_graph(n)[x]] for x in nx.wheel_graph(n)}
        assert a == b, n


def test_cycle_native_fast_path_reenabled():
    """Generators arc: cycle kernel's closing edge now emits (n-1, 0)
    LAST like nx's cyclic pairwise — native route re-enabled."""
    for n in range(0, 13):
        a = {repr(x): [repr(y) for y in fnx.cycle_graph(n)[x]] for x in fnx.cycle_graph(n)}
        b = {repr(x): [repr(y) for y in nx.cycle_graph(n)[x]] for x in nx.cycle_graph(n)}
        assert a == b, n
    # fallback paths unchanged
    a = {repr(x): [repr(y) for y in fnx.cycle_graph(["a", "b", "c"])[x]] for x in fnx.cycle_graph(["a", "b", "c"])}
    b = {repr(x): [repr(y) for y in nx.cycle_graph(["a", "b", "c"])[x]] for x in nx.cycle_graph(["a", "b", "c"])}
    assert a == b
