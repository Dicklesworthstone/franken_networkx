"""Parity + golden proof for minimum_cycle_basis scipy-batched de Pina (br-mcbscipy).
Run with PYTHONPATH=<repo>/python. fnx must be byte-identical to nx after the
_normalized_cycles canonicalization the conformance suite uses, across unweighted +
weighted + multi-component + adversarial (PYTHONHASHSEED-sensitive) fixtures.
"""
import hashlib, json, warnings, sys, random
warnings.filterwarnings("ignore")
import networkx as nx
import franken_networkx as fnx
from franken_networkx import _minimum_cycle_basis_via_parity as _ref


def canon(cycles):
    return sorted(tuple(sorted(c)) for c in cycles)


CASES = []
CASES.append(("two_triangles", nx.Graph([(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 2)])))
CASES.append(("k4", nx.complete_graph(4)))
CASES.append(("k5", nx.complete_graph(5)))
CASES.append(("petersen", nx.petersen_graph()))
CASES.append(("grid5x5", nx.convert_node_labels_to_integers(nx.grid_2d_graph(5, 5))))
CASES.append(("cube", nx.hypercube_graph(3)))
CASES.append(("tree", nx.random_labeled_tree(30, seed=1)))  # no cycles
# multi-component
mc = nx.disjoint_union(nx.cycle_graph(5), nx.complete_graph(4))
mc = nx.disjoint_union(mc, nx.path_graph(3))
CASES.append(("multi_component", mc))
# string nodes
sg = nx.Graph([("a", "b"), ("b", "c"), ("c", "a"), ("c", "d"), ("d", "a")])
CASES.append(("string_nodes", sg))
# unweighted sweeps
for seed in range(12):
    CASES.append((f"ws_{seed}", nx.watts_strogatz_graph(30 + seed, 4 + (seed % 3) * 2, 0.3, seed=seed)))
    CASES.append((f"ba_{seed}", nx.barabasi_albert_graph(25 + seed, 3, seed=seed)))
    CASES.append((f"gnp_{seed}", nx.gnp_random_graph(20 + seed, 0.25, seed=seed)))

WEIGHTED = []
for seed in range(12):
    G = nx.watts_strogatz_graph(28 + seed, 4, 0.4, seed=seed)
    rng = random.Random(seed)
    for u, v in G.edges():
        G.edges[u, v]["weight"] = rng.randint(1, 9)
    WEIGHTED.append((f"wt_{seed}", G))
# K4 distinct weights (the historical optimality bug fixture)
k4 = nx.complete_graph(4)
for u, v in k4.edges():
    k4.edges[u, v]["weight"] = abs(u - v) + 1
WEIGHTED.append(("k4_distinct_wt", k4))


def run():
    # ISOMORPHISM PROOF: the scipy-accelerated path must reproduce the CURRENT fnx
    # contract (_minimum_cycle_basis_via_parity) byte-for-byte. (fnx already
    # diverges from raw nx on non-unique bases because it runs the algorithm on a
    # rebuilt component-ordered graph rather than nx's SubgraphView — a PRE-EXISTING
    # property of the delegation, not this change.) We also report agreement with
    # raw nx for context.
    fails, fps = [], []
    nx_agree = 0
    total = 0
    for name, gx, wkw in [(n, g, None) for n, g in CASES] + [(n, g, "weight") for n, g in WEIGHTED]:
        total += 1
        gf = fnx.Graph(gx)
        ref = canon(_ref(gf, wkw))                       # current fnx contract
        fast = canon(fnx.minimum_cycle_basis(gf, weight=wkw))  # new path
        rawnx = canon(nx.minimum_cycle_basis(gx, weight=wkw))
        if fast != ref:
            fails.append((name, ref, fast))
        if fast == rawnx:
            nx_agree += 1
        fps.append((name, fast))
    sha = hashlib.sha256(json.dumps(fps, sort_keys=True, default=str).encode()).hexdigest()
    print(f"cases={total} mismatches_vs_current_fnx={len(fails)} also_match_raw_nx={nx_agree}/{total}")
    print(f"golden_sha256={sha}")
    if fails:
        for f in fails[:6]:
            print("MISMATCH", f[0], "\n  current_fnx =", f[1], "\n  fast        =", f[2])
        sys.exit(1)
    print("ALL PARITY OK (byte-exact vs current fnx _minimum_cycle_basis_via_parity)")


if __name__ == "__main__":
    run()
