"""Proof + bench harness for br-estrada-eigvalsh.

estrada_index = trace(expm(A)) = sum(exp(eigenvalues(A_unweighted))).
The new path computes eigenvalues via eigvalsh (no eigenvectors); the old
path summed subgraph_centrality (full eigh).  Both equal nx within float
tolerance.  This harness:
  1. Golden: across a corpus, compares fnx (new) vs genuine nx and vs the
     old sum(subgraph_centrality) formulation; reports max relative error
     and a rounded-value SHA256 over the whole corpus.
  2. Bench: warm min-of-N timing, old-vs-new, on a representative graph.
"""
import hashlib, json, sys, time
import numpy as np
import networkx as nx
import franken_networkx as fnx

genuine_estrada = getattr(nx.estrada_index, "orig_func", nx.estrada_index)


def old_formulation(G):
    """Pre-change path: sum of subgraph_centrality (full eigh)."""
    return sum(fnx.subgraph_centrality(G).values())


def build_corpus():
    out = []
    out.append(("path10", nx.path_graph(10)))
    out.append(("cycle12", nx.cycle_graph(12)))
    out.append(("complete8", nx.complete_graph(8)))
    out.append(("karate", nx.karate_club_graph()))
    out.append(("petersen", nx.petersen_graph()))
    out.append(("star20", nx.star_graph(20)))
    out.append(("wheel15", nx.wheel_graph(15)))
    for seed in range(8):
        out.append((f"gnp40_{seed}", nx.gnp_random_graph(40, 0.15, seed=seed)))
    for seed in range(4):
        out.append((f"ws120_{seed}", nx.connected_watts_strogatz_graph(120, 6, 0.3, seed=seed)))
    out.append(("ba200", nx.barabasi_albert_graph(200, 3, seed=1)))
    out.append(("single", nx.empty_graph(1)))
    out.append(("empty", nx.empty_graph(0)))
    return out


def to_fnx(G):
    fg = fnx.Graph()
    fg.add_nodes_from(list(G.nodes()))
    fg.add_edges_from(list(G.edges()))
    return fg


def golden():
    max_rel_nx = 0.0
    max_rel_old = 0.0
    rounded = []
    for name, G in build_corpus():
        fg = to_fnx(G)
        fv = fnx.estrada_index(fg)
        nv = genuine_estrada(G)
        ov = old_formulation(fg)
        # type contract: empty graph -> int 0
        if G.number_of_nodes() == 0:
            assert isinstance(fv, int) and fv == 0, f"{name}: empty must be int 0, got {fv!r}"
        denom = abs(nv) if nv else 1.0
        rel_nx = abs(fv - nv) / denom
        rel_old = abs(fv - ov) / (abs(ov) if ov else 1.0)
        max_rel_nx = max(max_rel_nx, rel_nx)
        max_rel_old = max(max_rel_old, rel_old)
        rounded.append((name, round(float(fv), 9)))
    sha = hashlib.sha256(
        json.dumps(rounded, sort_keys=True).encode()
    ).hexdigest()
    return max_rel_nx, max_rel_old, sha


def bench(n_runs=9):
    G = nx.connected_watts_strogatz_graph(400, 6, 0.3, seed=7)
    fg = to_fnx(G)

    def warm_min(fn, runs):
        for _ in range(2):
            fn()
        best = min(_time(fn) for _ in range(runs))
        return best

    def _time(fn):
        s = time.perf_counter()
        fn()
        return (time.perf_counter() - s) * 1000

    t_new = warm_min(lambda: fnx.estrada_index(fg), n_runs)
    t_old = warm_min(lambda: old_formulation(fg), n_runs)
    t_nx = warm_min(lambda: genuine_estrada(G), n_runs)
    return t_new, t_old, t_nx


if __name__ == "__main__":
    max_rel_nx, max_rel_old, sha = golden()
    t_new, t_old, t_nx = bench()
    report = {
        "golden": {
            "max_rel_err_vs_nx": max_rel_nx,
            "max_rel_err_vs_old": max_rel_old,
            "corpus_rounded_sha256": sha,
            "tolerance_used_by_conformance": 1e-6,
            "within_tolerance": max_rel_nx < 1e-6,
        },
        "bench_ws400_ms_warm_min": {
            "new_eigvalsh": round(t_new, 3),
            "old_sum_subgraph_centrality": round(t_old, 3),
            "genuine_nx": round(t_nx, 3),
            "speedup_vs_old": round(t_old / t_new, 3),
            "speedup_vs_nx": round(t_nx / t_new, 3),
        },
    }
    print(json.dumps(report, indent=2))
