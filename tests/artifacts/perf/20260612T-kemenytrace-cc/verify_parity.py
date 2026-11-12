"""Parity + golden proof for kemeny_constant trace-of-inverse (br-kemenytrace).
Run with PYTHONPATH=<repo>/python. Compares fnx vs nx across small (eigvalsh path,
bit-exact) and large (Cholesky path, ~1e-14) graphs; emits golden sha of rounded vals.
"""
import hashlib, json, warnings, sys
warnings.filterwarnings("ignore")
import numpy as np, networkx as nx
import franken_networkx as fnx

CASES = []
CASES.append(("complete5", nx.complete_graph(5)))
CASES.append(("complete40", nx.complete_graph(40)))
CASES.append(("path10", nx.path_graph(10)))
CASES.append(("cycle20", nx.cycle_graph(20)))
CASES.append(("bipartite_15_20", nx.complete_bipartite_graph(15, 20)))
CASES.append(("petersen", nx.petersen_graph()))
CASES.append(("karate", nx.karate_club_graph()))
CASES.append(("ws150", nx.watts_strogatz_graph(150, 6, 0.3, seed=1)))   # below gate
CASES.append(("ws256", nx.watts_strogatz_graph(256, 6, 0.3, seed=1)))   # at gate
CASES.append(("ws300", nx.watts_strogatz_graph(300, 6, 0.3, seed=1)))   # above gate
CASES.append(("ba500", nx.barabasi_albert_graph(500, 4, seed=1)))
CASES.append(("ws1000", nx.watts_strogatz_graph(1000, 6, 0.3, seed=2)))
CASES.append(("grid20", nx.grid_2d_graph(20, 20)))
# self-loops
sl = nx.path_graph(300); sl.add_edge(0, 0); sl.add_edge(150, 150)
CASES.append(("selfloops300", sl))
# weighted large
wg = nx.barabasi_albert_graph(400, 4, seed=3)
for u, v in wg.edges(): wg.edges[u, v]["weight"] = 1.0 + ((u * 7 + v) % 5)
CASES.append(("weighted400", wg))
# weighted small
ws = nx.barabasi_albert_graph(60, 4, seed=3)
for u, v in ws.edges(): ws.edges[u, v]["weight"] = 1.0 + ((u * 7 + v) % 5)
CASES.append(("weighted60", ws))


def run():
    fails, fps = [], []
    worst = 0.0
    for name, gx in CASES:
        weighted = any("weight" in d for _, _, d in gx.edges(data=True))
        wkw = "weight" if weighted else None
        gf = fnx.Graph(gx)
        kn = nx.kemeny_constant(gx, weight=wkw)
        kf = fnx.kemeny_constant(gf, weight=wkw)
        rel = abs(kn - kf) / abs(kn) if kn else abs(kn - kf)
        worst = max(worst, rel)
        if rel > 1e-9:
            fails.append((name, kn, kf, rel))
        fps.append((name, round(kf, 9)))
    sha = hashlib.sha256(json.dumps(fps, sort_keys=True).encode()).hexdigest()
    print(f"cases={len(CASES)} worst_rel_err={worst:.2e} fails(>1e-9)={len(fails)}")
    print(f"golden_sha256={sha}")
    if fails:
        for f in fails: print("FAIL", f)
        sys.exit(1)
    print("ALL PARITY OK (rel err < 1e-9 vs networkx)")


if __name__ == "__main__":
    run()
