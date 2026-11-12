"""CGSE collection-mode fallback: armed-vs-unarmed equivalence + witness emission.

This test proves the CGSE-(A) contract for every delegated public traversal:

  1. **Transparency.** When witness collection is armed, each function returns the
     *same materialized output in the same order* as the unarmed streaming/Python
     path. A caller cannot tell from the result whether collection was armed.
  2. **The fallback actually fires.** Armed, each delegated function routes through
     the instrumented eager kernel and therefore emits >= 1 CGSE witness. Without
     the fix the armed call takes the uninstrumented streaming path and emits zero,
     so every `witnesses` assertion below fails on `eab1cd44` (fail-before), and
     passes once the `if _cgse_armed():` prologue is in place (pass-after).

Graph families cover directed and undirected, connected and disconnected, empty,
single-node, and self-loops, over several seeds. Generators are fully materialized
before comparison so ordering is checked, not just set-equality.
"""

import random

import pytest

import franken_networkx as fnx
from franken_networkx._fnx import cgse


# --------------------------------------------------------------------------- #
# Seeded graph builders (built with the stdlib RNG, so the fixtures do not     #
# depend on any fnx generator being correct).                                  #
# --------------------------------------------------------------------------- #
def _undirected_graphs():
    """(label, G) pairs of undirected fnx graphs."""
    out = []

    g = fnx.Graph()
    out.append(("empty", g))

    g = fnx.Graph()
    g.add_node(0)
    out.append(("singleton", g))

    g = fnx.Graph()
    g.add_node(0)
    g.add_edge(0, 0)  # self-loop
    out.append(("singleton_selfloop", g))

    g = fnx.Graph()
    g.add_edges_from([(0, 1), (1, 2), (2, 0), (3, 4)])  # a triangle + a disjoint edge
    g.add_node(5)  # isolated
    out.append(("two_comps_plus_isolate", g))

    for seed in (1, 7, 42):
        for n in (10, 30):
            rng = random.Random(seed * 1000 + n)
            g = fnx.Graph()
            g.add_nodes_from(range(n))
            for u in range(n):
                for v in range(u + 1, n):
                    if rng.random() < 0.18:
                        g.add_edge(u, v)
            # sprinkle a few self-loops
            for _ in range(n // 10):
                x = rng.randrange(n)
                g.add_edge(x, x)
            out.append((f"gnp_u_s{seed}_n{n}", g))
    return out


def _directed_graphs():
    """(label, G) pairs of directed fnx graphs."""
    out = []

    g = fnx.DiGraph()
    out.append(("empty", g))

    g = fnx.DiGraph()
    g.add_node(0)
    out.append(("singleton", g))

    g = fnx.DiGraph()
    g.add_node(0)
    g.add_edge(0, 0)  # self-loop
    out.append(("singleton_selfloop", g))

    g = fnx.DiGraph()
    # one strong 3-cycle, a pendant, and a disjoint 2-cycle
    g.add_edges_from([(0, 1), (1, 2), (2, 0), (2, 3), (4, 5), (5, 4)])
    g.add_node(6)  # isolated
    out.append(("mixed_scc", g))

    for seed in (1, 7, 42):
        for n in (10, 30):
            rng = random.Random(seed * 2000 + n)
            g = fnx.DiGraph()
            g.add_nodes_from(range(n))
            for u in range(n):
                for v in range(n):
                    if u != v and rng.random() < 0.10:
                        g.add_edge(u, v)
            for _ in range(n // 10):
                x = rng.randrange(n)
                g.add_edge(x, x)
            out.append((f"gnp_d_s{seed}_n{n}", g))
    return out


def _armed(call):
    """Run ``call`` with CGSE witness collection armed; return (result, n_witnesses)."""
    result, witnesses = cgse.collect_witnesses(call)
    return result, len(witnesses)


def _substantive(G):
    return G.number_of_nodes() >= 2 and G.number_of_edges() >= 1


# --------------------------------------------------------------------------- #
# bfs_edges: directed and undirected, from a present source                    #
# --------------------------------------------------------------------------- #
def test_bfs_edges_fallback_equiv():
    cases = [("U", g[0], g[1]) for g in _undirected_graphs()] + [
        ("D", g[0], g[1]) for g in _directed_graphs()
    ]
    for kind, label, G in cases:
        if G.number_of_nodes() == 0:
            continue
        src = next(iter(G.nodes()))
        unarmed = list(fnx.bfs_edges(G, src))
        armed, nw = _armed(lambda: list(fnx.bfs_edges(G, src)))
        assert armed == unarmed, f"bfs_edges order/output diverged on {kind}:{label}"
        if _substantive(G):
            assert nw >= 1, f"bfs_edges emitted no witness armed on {kind}:{label}"


# --------------------------------------------------------------------------- #
# dfs_edges: directed and undirected, from a present source AND source=None    #
# --------------------------------------------------------------------------- #
def test_dfs_edges_fallback_equiv():
    cases = [("U", g[0], g[1]) for g in _undirected_graphs()] + [
        ("D", g[0], g[1]) for g in _directed_graphs()
    ]
    for kind, label, G in cases:
        srcs = [None]
        if G.number_of_nodes():
            srcs.append(next(iter(G.nodes())))
        for src in srcs:
            unarmed = list(fnx.dfs_edges(G, source=src))
            armed, nw = _armed(lambda: list(fnx.dfs_edges(G, source=src)))
            assert armed == unarmed, (
                f"dfs_edges order/output diverged on {kind}:{label} src={src!r}"
            )
            if src is None and _substantive(G):
                assert nw >= 1, (
                    f"dfs_edges emitted no witness armed on {kind}:{label} src=None"
                )


# --------------------------------------------------------------------------- #
# connected_components: undirected only (generator of sets, order checked)      #
# --------------------------------------------------------------------------- #
def test_connected_components_fallback_equiv():
    for label, G in _undirected_graphs():
        unarmed = list(fnx.connected_components(G))
        armed, nw = _armed(lambda: list(fnx.connected_components(G)))
        assert armed == unarmed, (
            f"connected_components component order/output diverged on {label}"
        )
        if _substantive(G):
            assert nw >= 1, f"connected_components emitted no witness armed on {label}"


# --------------------------------------------------------------------------- #
# strongly_connected_components: directed only (generator of sets)              #
# --------------------------------------------------------------------------- #
def test_strongly_connected_components_fallback_equiv():
    for label, G in _directed_graphs():
        unarmed = list(fnx.strongly_connected_components(G))
        armed, nw = _armed(lambda: list(fnx.strongly_connected_components(G)))
        assert armed == unarmed, (
            f"strongly_connected_components order/output diverged on {label}"
        )
        if _substantive(G):
            assert nw >= 1, (
                f"strongly_connected_components emitted no witness armed on {label}"
            )


# --------------------------------------------------------------------------- #
# Return TYPE is preserved (caller cannot tell collection was armed).          #
# --------------------------------------------------------------------------- #
def test_return_shape_matches_unarmed():
    gU = fnx.Graph()
    gU.add_edges_from([(0, 1), (1, 2), (3, 4)])
    gD = fnx.DiGraph()
    gD.add_edges_from([(0, 1), (1, 0), (2, 3)])

    pairs = [
        lambda: fnx.bfs_edges(gU, 0),
        lambda: fnx.dfs_edges(gU, source=0),
        lambda: fnx.connected_components(gU),
        lambda: fnx.strongly_connected_components(gD),
    ]
    for make in pairs:
        unarmed_t = type(make())
        armed_obj, _ = cgse.collect_witnesses(make)
        assert type(armed_obj) is unarmed_t, (
            f"return type changed under collection: {type(armed_obj)} != {unarmed_t}"
        )


# --------------------------------------------------------------------------- #
# Armed laziness under mutation: cc/scc must defer to first advance             #
# exactly like the unarmed generator, so a graph mutation BETWEEN creating the  #
# generator and consuming it is reflected identically. This fails on a call-    #
# time (eager generator-expression) armed branch, which computes at call time.  #
# --------------------------------------------------------------------------- #
def test_cc_armed_laziness_under_mutation():
    def run():
        G = fnx.Graph()
        G.add_edges_from([(0, 1), (2, 3)])  # two components
        gen = fnx.connected_components(G)   # create generator (not yet advanced)
        G.add_edge(1, 2)                    # bridge AFTER create, BEFORE consume
        return [set(c) for c in gen]        # consume -> must see the bridge

    unarmed = run()
    armed, _ = cgse.collect_witnesses(run)
    # control: the unarmed generator is lazy, so the bridge merges to one component
    assert any(len(c) == 4 for c in unarmed), f"control: unarmed did not defer: {unarmed}"
    assert armed == unarmed, (
        f"connected_components armed laziness broke under mutation: "
        f"armed={armed} unarmed={unarmed}"
    )


def test_scc_armed_laziness_under_mutation():
    def run():
        D = fnx.DiGraph()
        D.add_edges_from([(0, 1), (1, 0), (2, 3), (3, 2)])  # two 2-cycles
        gen = fnx.strongly_connected_components(D)
        D.add_edges_from([(1, 2), (2, 1)])                  # bridge into one SCC
        return [set(c) for c in gen]

    unarmed = run()
    armed, _ = cgse.collect_witnesses(run)
    assert any(len(c) == 4 for c in unarmed), f"control: unarmed did not defer: {unarmed}"
    assert armed == unarmed, (
        f"strongly_connected_components armed laziness broke under mutation: "
        f"armed={armed} unarmed={unarmed}"
    )


# --------------------------------------------------------------------------- #
# dijkstra_path on MultiDiGraph (unweighted): armed routes to the instrumented  #
# native kernel; unarmed stays pure-Python. Must be identical (incl exception)  #
# and emit >= 1 witness on every real path. Seeded, tie-heavy.                   #
# --------------------------------------------------------------------------- #
def test_dijkstra_mdg_unweighted_fallback_equiv():
    import random

    rng = random.Random(4242)
    for trial in range(30):
        n = rng.randint(2, 9)
        G = fnx.MultiDiGraph()
        G.add_nodes_from(range(n))
        for _ in range(rng.randint(n, 2 * n)):
            G.add_edge(rng.randrange(n), rng.randrange(n))
        for s in range(n):
            for t in range(n):
                try:
                    un = ("ok", list(fnx.dijkstra_path(G, s, t, weight=None)))
                except Exception as e:
                    un = ("exc", type(e).__name__, str(e))
                try:
                    r, w = cgse.collect_witnesses(lambda: fnx.dijkstra_path(G, s, t, weight=None))
                    ar, nw = ("ok", list(r)), len(w)
                except Exception as e:
                    ar, nw = ("exc", type(e).__name__, str(e)), 0
                assert ar == un, (
                    "dijkstra MDG armed != unarmed (trial=%d s=%d t=%d): %s vs %s"
                    % (trial, s, t, ar, un)
                )
                if un[0] == "ok":
                    assert nw >= 1, (
                        "dijkstra MDG emitted no witness on a real path (trial=%d s=%d t=%d)"
                        % (trial, s, t)
                    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
