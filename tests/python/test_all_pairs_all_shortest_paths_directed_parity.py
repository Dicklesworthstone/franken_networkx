"""Parity for ``all_pairs_all_shortest_paths`` directed reachability.

The native ``all_pairs_all_shortest_paths_rust`` kernel ignored edge
direction and emitted reverse paths to unreachable targets (e.g. on
``[(0,1),(1,2),(0,2)]`` it returned ``1 -> 0`` as ``[[1, 0]]``). The
unweighted directed path now builds from the directed-correct
``single_source_all_shortest_paths`` per source. br-r37-c1-s1czw
"""

from __future__ import annotations

import random
import sys

import pytest
import networkx as nx
import franken_networkx as fnx


def _norm(pairs_iter):
    return {
        s: {t: sorted(map(tuple, paths)) for t, paths in d.items()}
        for s, d in pairs_iter
    }


def _pair(seed, directed, p=0.35):
    rng = random.Random(seed)
    n = rng.randint(4, 8)
    fnx_cls, nx_cls = (fnx.DiGraph, nx.DiGraph) if directed else (fnx.Graph, nx.Graph)
    fg = fnx_cls()
    ng = nx_cls()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(n):
            if u == v:
                continue
            if (directed or u < v) and rng.random() < p:
                fg.add_edge(u, v)
                ng.add_edge(u, v)
    return fg, ng


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("seed", range(60))
def test_all_pairs_all_shortest_paths_matches_networkx(directed, seed):
    fg, ng = _pair(seed, directed)
    assert _norm(fnx.all_pairs_all_shortest_paths(fg)) == _norm(
        nx.all_pairs_all_shortest_paths(ng)
    )


def test_directed_does_not_emit_reverse_paths():
    # Regression: only forward-reachable targets appear.
    fg = fnx.DiGraph([(0, 1), (1, 2), (0, 2)])
    result = dict(fnx.all_pairs_all_shortest_paths(fg))
    # Node 2 is a sink: it reaches only itself.
    assert result[2] == {2: [[2]]}
    # Node 1 reaches 1 and 2, never 0.
    assert set(result[1]) == {1, 2}
    assert dict(fnx.all_pairs_all_shortest_paths(fg)) == {
        s: d for s, d in nx.all_pairs_all_shortest_paths(nx.DiGraph([(0, 1), (1, 2), (0, 2)]))
    }


def test_directed_self_paths_and_reachability_match_networkx():
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    for graph in (fg, ng):
        graph.add_nodes_from(["source", "mid", "sink", "other", "isolated"])
        graph.add_edges_from([
            ("source", "mid"),
            ("mid", "sink"),
            ("other", "mid"),
        ])

    result = dict(fnx.all_pairs_all_shortest_paths(fg))
    expected = dict(nx.all_pairs_all_shortest_paths(ng))

    assert result == expected
    assert result["sink"] == {"sink": [["sink"]]}
    assert result["isolated"] == {"isolated": [["isolated"]]}
    assert "source" not in result["mid"]


def test_weighted_still_matches_networkx():
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    for u, v, w in [(0, 1, 2), (1, 2, 1), (0, 2, 5)]:
        fg.add_edge(u, v, weight=w)
        ng.add_edge(u, v, weight=w)
    assert _norm(fnx.all_pairs_all_shortest_paths(fg, weight="weight")) == _norm(
        nx.all_pairs_all_shortest_paths(ng, weight="weight")
    )


@pytest.mark.skipif(sys.platform != "linux", reason="memory bound requires Linux /proc")
@pytest.mark.parametrize("cls", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("weight", [None, "weight"])
def test_all_pairs_all_shortest_paths_does_not_compute_later_sources(cls, weight):
    import subprocess
    import textwrap

    # The first source is isolated. A separate component has over a billion
    # equal shortest paths, which must not be enumerated to yield that source.
    script = textwrap.dedent(
        """
        from pathlib import Path
        import os
        import resource
        import sys

        import franken_networkx as fnx
        import networkx as nx

        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        vm_pages = int(Path("/proc/self/statm").read_text().split()[0])
        memory_limit = vm_pages * os.sysconf("SC_PAGE_SIZE") + 256 * 1024 * 1024
        _, hard_limit = resource.getrlimit(resource.RLIMIT_AS)
        if hard_limit != resource.RLIM_INFINITY:
            memory_limit = min(memory_limit, hard_limit)
        resource.setrlimit(resource.RLIMIT_AS, (memory_limit, hard_limit))

        cls, weighted = sys.argv[1:]
        edges = [(0, 1), (0, 2), (59, 61), (60, 61)]
        for layer in range(29):
            edges.extend(
                (u, v)
                for u in (2 * layer + 1, 2 * layer + 2)
                for v in (2 * layer + 3, 2 * layer + 4)
            )
        results = []
        for module in (nx, fnx):
            graph = getattr(module, cls)()
            graph.add_node("isolated")
            graph.add_nodes_from(range(62))
            graph.add_edges_from(edges, weight=1)
            if graph.is_multigraph():
                graph.add_edges_from(edges, weight=2)
            paths = module.all_pairs_all_shortest_paths(
                graph, weight="weight" if weighted == "yes" else None
            )
            results.append(next(paths))
            paths.close()
        assert results[1] == results[0] == ("isolated", {"isolated": [["isolated"]]})
        """
    )
    completed = subprocess.run(
        [sys.executable, "-c", script, cls, "yes" if weight is not None else "no"],
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    assert completed.returncode == 0, completed.stderr


@pytest.mark.parametrize("cls", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("method", ["unweighted", "dijkstra", "bellman-ford"])
def test_all_pairs_all_shortest_paths_observes_mutation_between_sources(cls, method):
    results = []
    kwargs = {} if method == "unweighted" else {"weight": "weight", "method": method}
    for module in (nx, fnx):
        graph = getattr(module, cls)()
        graph.add_nodes_from(["isolated", "source", "right", "left", "target"])
        graph.add_edges_from(
            [("source", "left"), ("left", "target"), ("source", "right"), ("right", "target")],
            weight=1,
        )
        paths = module.all_pairs_all_shortest_paths(graph, **kwargs)
        first = next(paths)
        graph.remove_edge("left", "target")
        graph.add_edge("source", "target", weight=2)
        remaining = [(source, list(targets.items())) for source, targets in paths]
        results.append((first, remaining))
    assert results[1] == results[0]
