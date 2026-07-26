#!/usr/bin/env python3
"""Paired fnx-vs-nx measurement harness — the §2 bench-harness contract.

Adopted 2026-07-25 (br-r37-c1-wbwkb, cc lane) from the fleet-wide contract in
`PERF_CAMPAIGN_2026-07-25`. Three properties, all mandatory:

1. **Self-reporting binary sha256.** The provenance header hashes the `_fnx`
   extension that is actually loaded and prints it as line 1. A hash computed by a
   shell step *next to* the run proves nothing about which ELF executed, and rch
   compiles into an opaque per-worker pool target dir.

2. **A/A null control in the same invocation.** Every row is measured twice:
   `paired(base, base)` establishes the noise floor, then `paired(base, cand)`.
   Both arms are timed INTERLEAVED inside one round with the order alternating per
   round, and the statistic is the **median of per-round ratios** — not a ratio of
   medians, which lets drift in either arm leak into the result.

3. **Gate on the median-CI, never on `cv`.** A claim is decidable iff its median
   ratio lies outside the A/A null's bootstrap 95% CI with a 2x margin in log
   space. `cv` is reported as provenance only. On this hardware `cv` does not track
   decidability: rows measured here at `cv 17.06%/5.52%` and `cv 0.44%/0.79%` had
   null CIs of `0.9997-1.0152` and `0.9947-1.0065` — a 30x spread in `cv` for a
   sub-2x spread in the decidable floor, ranked in the opposite order.

Knobs follow §2.4: `min_sample ~2 ms`, `min_of = 3` inner replicates keeping the
minimum (the dominant knob; longer samples are a bigger target for preemption).

Usage:
    python3 scripts/perf_harness.py view-accessors
    python3 scripts/perf_harness.py adj-descriptor
    python3 scripts/perf_harness.py adj-len
    python3 scripts/perf_harness.py adj-iter
    python3 scripts/perf_harness.py multi-adj-iter
    python3 scripts/perf_harness.py multi-adj-contains
    python3 scripts/perf_harness.py digraph-descriptors
    python3 scripts/perf_harness.py multidigraph-descriptors
    python3 scripts/perf_harness.py node-primitives
    python3 scripts/perf_harness.py nodeview-getitem
    python3 scripts/perf_harness.py lazy-rows
    python3 scripts/perf_harness.py marshaling

Point `PYTHONPATH` at the package tree under test; the header records which one ran.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import statistics
import sys
from dataclasses import dataclass, field
from time import perf_counter

MIN_SAMPLE_S = 0.002
MIN_OF = 3
ROUNDS = 21

# The nx arm must be genuinely unpatched upstream: a "2.6x faster" claim in this
# repo's history was once measured against an already-dispatched fnx baseline and
# genuine NetworkX turned out to be 1.88x FASTER. Clear the dispatch env first.
for _var in ("NETWORKX_AUTOMATIC_BACKENDS", "NETWORKX_BACKEND_PRIORITY", "NETWORKX_FALLBACK_TO_NX"):
    os.environ.pop(_var, None)


# --------------------------------------------------------------------------- #
# provenance
# --------------------------------------------------------------------------- #
def binary_sha256() -> tuple[str, str, int]:
    """Path + sha256 + size of the `_fnx` extension module actually loaded."""
    import franken_networkx._fnx as _fnx

    path = _fnx.__file__
    digest = hashlib.sha256()
    byte_count = 0
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
            byte_count += len(chunk)
    return path, digest.hexdigest(), byte_count


def provenance_header(tag: str) -> dict:
    import networkx as nx
    import franken_networkx as fnx

    path, sha, byte_count = binary_sha256()
    # Fleet contract: this exact loaded-artifact identity is line one. A shell
    # hash adjacent to the invocation cannot prove which worker-pool ELF ran.
    print(f"bench_elf_sha256={sha} ({byte_count} bytes) {path}", flush=True)
    wrapper_path = fnx.__file__
    wrapper_digest = hashlib.sha256()
    with open(wrapper_path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            wrapper_digest.update(chunk)
    info = {
        "tag": tag,
        "fnx_so": path,
        "fnx_so_sha256": sha,
        "fnx_so_bytes": byte_count,
        "fnx_python": wrapper_path,
        "fnx_python_sha256": wrapper_digest.hexdigest(),
        "nx_version": nx.__version__,
        "nx_file": nx.__file__,
        "python": sys.version.split()[0],
        "pid": os.getpid(),
        "loadavg": os.getloadavg(),
    }
    print(json.dumps(info), flush=True)
    return info


# --------------------------------------------------------------------------- #
# timing
# --------------------------------------------------------------------------- #
def _time_batch(fn, inner: int) -> float:
    start = perf_counter()
    for _ in range(inner):
        fn()
    return (perf_counter() - start) / inner


def calibrate(fn, target_s: float = MIN_SAMPLE_S) -> int:
    inner = 1
    while True:
        elapsed = _time_batch(fn, inner) * inner
        if elapsed >= target_s or inner >= 1 << 20:
            return max(1, inner)
        inner *= max(2, min(64, int(target_s / max(elapsed, 1e-9)) + 1))


def _sample(fn, inner: int, min_of: int = MIN_OF) -> float:
    return min(_time_batch(fn, inner) for _ in range(min_of))


@dataclass
class PairedResult:
    label: str
    ratio_p50: float
    ratio_ci: tuple[float, float]
    p50_a: float
    p50_b: float
    cv_a: float
    cv_b: float
    mad_ratio: float
    wins: str
    rounds: int
    checksum_a: str = ""
    checksum_b: str = ""
    ratios: list[float] = field(default_factory=list)


def _median_ci(values: list[float], iters: int = 2000, seed: int = 12345) -> tuple[float, float]:
    """Percentile bootstrap 95% CI of the median (fixed seed => reproducible)."""
    import random

    rng = random.Random(seed)
    n = len(values)
    medians = sorted(statistics.median(rng.choices(values, k=n)) for _ in range(iters))
    return medians[int(0.025 * iters)], medians[min(iters - 1, int(0.975 * iters))]


def paired(label: str, arm_a, arm_b, rounds: int = ROUNDS, min_of: int = MIN_OF) -> PairedResult:
    """Interleave both arms inside each round, alternating order per round.

    ratio = t_a / t_b, so ratio > 1 means arm_b is faster. With arm_a = networkx
    and arm_b = franken_networkx this reads as "fnx is Nx faster", matching the
    ledger convention.
    """
    inner_a, inner_b = calibrate(arm_a), calibrate(arm_b)
    _sample(arm_a, inner_a, 1)
    _sample(arm_b, inner_b, 1)

    times_a, times_b, ratios = [], [], []
    for round_index in range(rounds):
        if round_index % 2 == 0:
            ta = _sample(arm_a, inner_a, min_of)
            tb = _sample(arm_b, inner_b, min_of)
        else:
            tb = _sample(arm_b, inner_b, min_of)
            ta = _sample(arm_a, inner_a, min_of)
        times_a.append(ta)
        times_b.append(tb)
        ratios.append(ta / tb)

    median_ratio = statistics.median(ratios)

    def cv(values):
        return statistics.pstdev(values) / statistics.fmean(values) * 100.0

    return PairedResult(
        label=label,
        ratio_p50=median_ratio,
        ratio_ci=_median_ci(ratios),
        p50_a=statistics.median(times_a),
        p50_b=statistics.median(times_b),
        cv_a=cv(times_a),
        cv_b=cv(times_b),
        mad_ratio=statistics.median([abs(r - median_ratio) for r in ratios]),
        wins=f"{sum(1 for r in ratios if r > 1.0)}/{len(ratios)}",
        rounds=rounds,
        ratios=ratios,
    )


def decidable(cand: PairedResult, null: PairedResult, margin: float = 2.0) -> tuple[bool, str]:
    edge = max(abs(math.log(null.ratio_ci[0])), abs(math.log(null.ratio_ci[1])))
    need = margin * edge
    return abs(math.log(cand.ratio_p50)) > need, (
        f"floor={math.exp(need):.4f}x "
        f"(null CI {null.ratio_ci[0]:.4f}-{null.ratio_ci[1]:.4f}, {margin:g}x margin)"
    )


def report(result: PairedResult, null: PairedResult | None = None) -> str:
    line = (
        f"{result.label:<54} ratio_p50={result.ratio_p50:9.4f}x "
        f"CI=[{result.ratio_ci[0]:.4f},{result.ratio_ci[1]:.4f}] "
        f"a={result.p50_a * 1e6:9.2f}us b={result.p50_b * 1e6:9.2f}us "
        f"cv={result.cv_a:5.2f}/{result.cv_b:5.2f}% wins={result.wins}"
    )
    if null is not None:
        ok, why = decidable(result, null)
        line += f"  -> {'DECIDABLE' if ok else 'UNDECIDABLE'} {why}"
    print(line, flush=True)
    return line


# --------------------------------------------------------------------------- #
# byte-identity proof
# --------------------------------------------------------------------------- #
def canon(obj):
    """Order-preserving canonical form — iteration order is part of the contract."""
    if isinstance(obj, dict):
        return ["<dict>"] + [[canon(k), canon(v)] for k, v in obj.items()]
    if isinstance(obj, (list, tuple)):
        return [canon(x) for x in obj]
    if isinstance(obj, (set, frozenset)):
        return ["<set>"] + sorted(canon(x) for x in obj)
    if hasattr(obj, "edges") and hasattr(obj, "nodes"):
        return ["<graph>", [canon(x) for x in obj.nodes()], [canon(e) for e in obj.edges()]]
    if hasattr(obj, "__iter__") and not isinstance(obj, (str, bytes, int, float)):
        return [canon(x) for x in obj]
    return obj


def digest(obj) -> str:
    return hashlib.sha256(
        json.dumps(canon(obj), sort_keys=False, default=str).encode()
    ).hexdigest()[:16]


def run_rows(tag: str, rows, rounds: int = ROUNDS) -> list[dict]:
    """Prove byte-identity, then measure each row against its own A/A null."""
    provenance_header(tag)
    results = []
    for label, arm_nx, arm_fnx in rows:
        left, right = arm_nx(), arm_fnx()
        da, db = digest(left), digest(right)
        if da != db:
            print(f"{label:<54} PARITY-DIVERGENCE nx={da} fnx={db} — NOT TIMED", flush=True)
            results.append({"label": label, "parity": "DIVERGENT"})
            continue
        null = paired(f"[A/A null] {label}", arm_nx, arm_nx, rounds=rounds)
        cand = paired(label, arm_nx, arm_fnx, rounds=rounds)
        report(null)
        report(cand, null)
        ok, _ = decidable(cand, null)
        results.append({
            "label": label,
            "parity": "IDENTICAL",
            "checksum": da,
            "ratio_p50": cand.ratio_p50,
            "ratio_ci": list(cand.ratio_ci),
            "null_ci": list(null.ratio_ci),
            "decidable": ok,
            "cv": [cand.cv_a, cand.cv_b],
        })
    return results


# --------------------------------------------------------------------------- #
# suites
# --------------------------------------------------------------------------- #
def _build_pair(n, m, seed, weighted, directed=False):
    """Same node/edge insertion order in both libraries."""
    import random

    import networkx as nx
    import franken_networkx as fnx

    rng = random.Random(seed)
    seen, stream = set(), []
    while len(stream) < m:
        u, v = rng.randrange(n), rng.randrange(n)
        if u == v or (min(u, v), max(u, v)) in seen:
            continue
        seen.add((min(u, v), max(u, v)))
        stream.append((str(u), str(v), {"weight": rng.randint(1, 20)} if weighted else {}))
    nodes = [str(i) for i in range(n)]
    gnx = (nx.DiGraph if directed else nx.Graph)()
    gfx = (fnx.DiGraph if directed else fnx.Graph)()
    gnx.add_nodes_from(nodes)
    gfx.add_nodes_from(nodes)
    gnx.add_edges_from([(u, v, dict(d)) for u, v, d in stream])
    gfx.add_edges_from([(u, v, dict(d)) for u, v, d in stream])
    assert type(gnx).__module__.startswith("networkx"), "nx arm must be genuine upstream"
    return gnx, gfx


def suite_view_accessors():
    """br-r37-c1-wbwkb: the accessor-descriptor surface."""
    gnx, gfx = _build_pair(2000, 8000, seed=7, weighted=True)
    nodes = [str(i) for i in range(500)]
    return [
        ("G.nodes x500 (bare accessor)",
         lambda: [gnx.nodes for _ in nodes], lambda: [gfx.nodes for _ in nodes]),
        ("G.edges x500 (bare accessor)",
         lambda: [gnx.edges for _ in nodes], lambda: [gfx.edges for _ in nodes]),
        ("G.degree x500 (bare accessor)",
         lambda: [gnx.degree for _ in nodes], lambda: [gfx.degree for _ in nodes]),
        ("G.adj x500 (bare accessor)",
         lambda: [gnx.adj for _ in nodes], lambda: [gfx.adj for _ in nodes]),
        ("G.nodes[n] x500",
         lambda: [gnx.nodes[n] for n in nodes], lambda: [gfx.nodes[n] for n in nodes]),
        ("G.degree[n] x500",
         lambda: [gnx.degree[n] for n in nodes], lambda: [gfx.degree[n] for n in nodes]),
        ("len(G.edges) x500",
         lambda: [len(gnx.edges) for _ in nodes], lambda: [len(gfx.edges) for _ in nodes]),
        ("sum(G.nodes[n]['weight']) x500",
         lambda: sum(gnx.nodes[n].get("weight", 0) for n in nodes),
         lambda: sum(gfx.nodes[n].get("weight", 0) for n in nodes)),
    ]


def suite_adj_descriptor():
    """br-r37-c1-pc4hk: cache public Graph.adj; retain private _adj setter."""
    import franken_networkx as fnx

    gnx, gfx = _build_pair(2000, 8000, seed=7, weighted=True)
    repeats = range(500)
    descriptor = fnx.Graph.__dict__["adj"]
    property_descriptor = fnx._GRAPH_PUBLIC_ADJ_PROPERTY
    raw_setattr = fnx._GRAPH_SETATTR_BEFORE_PUBLIC_ADJ_CACHE
    candidate_setattr = fnx._graph_setattr_with_cached_public_adj
    assert isinstance(descriptor, fnx._CachedViewDescriptor)
    _ = gfx.adj

    def property_accessor():
        return [property_descriptor.__get__(gfx, fnx.Graph) for _ in repeats]

    def cached_accessor():
        return [gfx.adj for _ in repeats]

    baseline_mut = fnx.Graph()
    candidate_mut = fnx.Graph()
    for graph in (baseline_mut, candidate_mut):
        graph.add_nodes_from(("left", "right"))

    def property_mutation():
        fnx.Graph.__setattr__ = raw_setattr
        fnx.Graph.adj = property_descriptor
        for _ in range(512):
            baseline_mut.add_edge("left", "right")
            baseline_mut.remove_edge("left", "right")
        return baseline_mut.number_of_edges()

    def cached_mutation():
        fnx.Graph.__setattr__ = candidate_setattr
        fnx.Graph.adj = descriptor
        for _ in range(512):
            candidate_mut.add_edge("left", "right")
            candidate_mut.remove_edge("left", "right")
        return candidate_mut.number_of_edges()

    return [
        (
            "G.adj x500 [property/cached]",
            property_accessor,
            cached_accessor,
        ),
        (
            "G.adj x500 [nx/fnx]",
            lambda: [gnx.adj for _ in repeats],
            cached_accessor,
        ),
        (
            "len(G.adj) x500 [nx/fnx]",
            lambda: [len(gnx.adj) for _ in repeats],
            lambda: [len(gfx.adj) for _ in repeats],
        ),
        (
            "add/remove edge x512 [property/cached]",
            property_mutation,
            cached_mutation,
        ),
    ]


def suite_adjacency_len():
    """br-r37-c1-4rgsf: outer simple adjacency views use raw node count."""
    import franken_networkx as fnx

    gnx, gfx = _build_pair(2000, 8000, seed=7, weighted=True)
    dnx, dfx = _build_pair(2000, 8000, seed=17, weighted=True, directed=True)
    repeats = range(500)
    graph_view = gfx.adj

    def atlas_len_x500():
        return [len(graph_view._atlas()) for _ in repeats]

    def native_len_x500():
        return [len(graph_view) for _ in repeats]

    return [
        (
            "len(G.adj) x500 [atlas/raw-bound]",
            atlas_len_x500,
            native_len_x500,
        ),
        (
            "len(G.adj) x500 [nx/fnx]",
            lambda: [len(gnx.adj) for _ in repeats],
            native_len_x500,
        ),
        (
            "len(DG.adj) x500 [nx/fnx]",
            lambda: [len(dnx.adj) for _ in repeats],
            lambda: [len(dfx.adj) for _ in repeats],
        ),
        (
            "len(DG.succ) x500 [nx/fnx]",
            lambda: [len(dnx.succ) for _ in repeats],
            lambda: [len(dfx.succ) for _ in repeats],
        ),
        (
            "len(DG.pred) x500 [nx/fnx]",
            lambda: [len(dnx.pred) for _ in repeats],
            lambda: [len(dfx.pred) for _ in repeats],
        ),
    ]


def suite_adjacency_iter():
    """br-r37-c1-krg59: outer simple views reuse the live node-key mirror."""
    gnx, gfx = _build_pair(20_000, 0, seed=7, weighted=False)
    dnx, dfx = _build_pair(
        20_000, 0, seed=17, weighted=False, directed=True
    )
    graph_view = gfx.adj
    digraph_view = dfx.adj
    assert graph_view._fnx_native_iter is not None
    assert digraph_view._fnx_native_iter is not None

    def old_graph_iter():
        return iter(dict.fromkeys(graph_view._atlas()))

    def old_digraph_iter():
        return iter(dict.fromkeys(digraph_view._atlas()))

    def old_graph_list():
        return list(old_graph_iter())

    def old_digraph_list():
        return list(old_digraph_iter())

    # Stabilize worker frequency before the first A/A round. Both mechanism
    # arms are warmed outside every timed region.
    warm_deadline = perf_counter() + 2.0
    while perf_counter() < warm_deadline:
        old_graph_iter()
        iter(graph_view)
        old_digraph_iter()
        iter(digraph_view)

    return [
        (
            "iter(G.adj) [fromkeys/raw-bound]",
            old_graph_iter,
            lambda: iter(graph_view),
        ),
        (
            "iter(DG.adj) [fromkeys/raw-bound]",
            old_digraph_iter,
            lambda: iter(digraph_view),
        ),
        (
            "list(G.adj) [fromkeys/raw-bound]",
            old_graph_list,
            lambda: list(graph_view),
        ),
        (
            "list(DG.adj) [fromkeys/raw-bound]",
            old_digraph_list,
            lambda: list(digraph_view),
        ),
        (
            "iter(G.adj) [nx/fnx]",
            lambda: iter(gnx.adj),
            lambda: iter(graph_view),
        ),
        (
            "list(G.adj) [nx/fnx]",
            lambda: list(gnx.adj),
            lambda: list(graph_view),
        ),
        (
            "iter(DG.adj) [nx/fnx]",
            lambda: iter(dnx.adj),
            lambda: iter(digraph_view),
        ),
        (
            "list(DG.adj) [nx/fnx]",
            lambda: list(dnx.adj),
            lambda: list(digraph_view),
        ),
        (
            "list(DG.succ) [nx/fnx]",
            lambda: list(dnx.succ),
            lambda: list(dfx.succ),
        ),
        (
            "list(DG.pred) [nx/fnx]",
            lambda: list(dnx.pred),
            lambda: list(dfx.pred),
        ),
    ]


def suite_multi_adjacency_iter():
    """br-r37-c1-yisq4: multigraph outer views reuse the node-key mirror."""
    import networkx as nx
    import franken_networkx as fnx

    gnx, gfx = nx.MultiGraph(), fnx.MultiGraph()
    dnx, dfx = nx.MultiDiGraph(), fnx.MultiDiGraph()
    nodes = range(20_000)
    for graph in (gnx, gfx, dnx, dfx):
        graph.add_nodes_from(nodes)
    graph_view = gfx.adj
    digraph_view = dfx.adj
    assert graph_view._fnx_native_iter is not None
    assert digraph_view._fnx_native_iter is not None

    def old_graph_iter():
        return iter(dict.fromkeys(graph_view._fnx_owner))

    def old_digraph_iter():
        return iter(dict.fromkeys(digraph_view._fnx_owner))

    def old_graph_list():
        return list(old_graph_iter())

    def old_digraph_list():
        return list(old_digraph_iter())

    warm_deadline = perf_counter() + 2.0
    while perf_counter() < warm_deadline:
        old_graph_iter()
        iter(graph_view)
        old_digraph_iter()
        iter(digraph_view)

    return [
        (
            "iter(MG.adj) [fromkeys/raw-bound]",
            old_graph_iter,
            lambda: iter(graph_view),
        ),
        (
            "iter(MDG.adj) [fromkeys/raw-bound]",
            old_digraph_iter,
            lambda: iter(digraph_view),
        ),
        (
            "list(MG.adj) [fromkeys/raw-bound]",
            old_graph_list,
            lambda: list(graph_view),
        ),
        (
            "list(MDG.adj) [fromkeys/raw-bound]",
            old_digraph_list,
            lambda: list(digraph_view),
        ),
        (
            "iter(MG.adj) [nx/fnx]",
            lambda: iter(gnx.adj),
            lambda: iter(graph_view),
        ),
        (
            "list(MG.adj) [nx/fnx]",
            lambda: list(gnx.adj),
            lambda: list(graph_view),
        ),
        (
            "iter(MDG.adj) [nx/fnx]",
            lambda: iter(dnx.adj),
            lambda: iter(digraph_view),
        ),
        (
            "list(MDG.adj) [nx/fnx]",
            lambda: list(dnx.adj),
            lambda: list(digraph_view),
        ),
        (
            "list(MDG.succ) [nx/fnx]",
            lambda: list(dnx.succ),
            lambda: list(dfx.succ),
        ),
        (
            "list(MDG.pred) [nx/fnx]",
            lambda: list(dnx.pred),
            lambda: list(dfx.pred),
        ),
    ]


def suite_multi_adjacency_contains():
    """br-r37-c1-7icpc: bind raw node membership into multigraph views."""
    import networkx as nx
    import franken_networkx as fnx

    node_names = [f"node-{index}" for index in range(20_000)]
    present = node_names[:512]
    missing = [f"missing-{index}" for index in range(512)]
    gnx, gfx = nx.MultiGraph(), fnx.MultiGraph()
    dnx, dfx = nx.MultiDiGraph(), fnx.MultiDiGraph()
    for graph in (gnx, gfx, dnx, dfx):
        graph.add_nodes_from(node_names)
    graph_view = gfx.adj
    digraph_view = dfx.adj
    assert graph_view._fnx_native_contains is not None
    assert digraph_view._fnx_native_contains is not None

    def old_contains(view, node):
        hash(node)
        owner = view._fnx_owner
        if owner is not None:
            return node in owner
        return node in view._atlas()

    def old_graph_present():
        return sum(old_contains(graph_view, node) for node in present)

    def new_graph_present():
        return sum(node in graph_view for node in present)

    def old_digraph_present():
        return sum(old_contains(digraph_view, node) for node in present)

    def new_digraph_present():
        return sum(node in digraph_view for node in present)

    def old_digraph_missing():
        return sum(old_contains(digraph_view, node) for node in missing)

    def new_digraph_missing():
        return sum(node in digraph_view for node in missing)

    warm_deadline = perf_counter() + 2.0
    while perf_counter() < warm_deadline:
        old_graph_present()
        new_graph_present()
        old_digraph_present()
        new_digraph_present()

    return [
        (
            "n in MG.adj x512 [owner-chain/raw-bound]",
            old_graph_present,
            new_graph_present,
        ),
        (
            "n in MDG.adj x512 [owner-chain/raw-bound]",
            old_digraph_present,
            new_digraph_present,
        ),
        (
            "missing in MDG.adj x512 [owner-chain/raw-bound]",
            old_digraph_missing,
            new_digraph_missing,
        ),
        (
            "n in MG.adj x512 [nx/fnx]",
            lambda: sum(node in gnx.adj for node in present),
            new_graph_present,
        ),
        (
            "missing in MG.adj x512 [nx/fnx]",
            lambda: sum(node in gnx.adj for node in missing),
            lambda: sum(node in graph_view for node in missing),
        ),
        (
            "n in MDG.adj x512 [nx/fnx]",
            lambda: sum(node in dnx.adj for node in present),
            new_digraph_present,
        ),
        (
            "n in MDG.succ x512 [nx/fnx]",
            lambda: sum(node in dnx.succ for node in present),
            lambda: sum(node in dfx.succ for node in present),
        ),
        (
            "n in MDG.pred x512 [nx/fnx]",
            lambda: sum(node in dnx.pred for node in present),
            lambda: sum(node in dfx.pred for node in present),
        ),
    ]


def suite_digraph_descriptors():
    """br-r37-c1-dyuzb: cache directed public adjacency descriptors."""
    import franken_networkx as fnx

    gnx, gfx = _build_pair(
        2000, 8000, seed=17, weighted=True, directed=True
    )
    repeats = range(500)
    properties = fnx._DIGRAPH_PUBLIC_ADJ_PROPERTIES
    assert all(
        isinstance(fnx.DiGraph.__dict__[name], fnx._CachedViewDescriptor)
        for name in ("adj", "succ", "pred")
    )
    _ = gfx.adj, gfx.succ, gfx.pred

    def property_triple():
        return [
            (
                properties["adj"].__get__(gfx, fnx.DiGraph),
                properties["succ"].__get__(gfx, fnx.DiGraph),
                properties["pred"].__get__(gfx, fnx.DiGraph),
            )
            for _ in repeats
        ]

    def cached_triple():
        return [(gfx.adj, gfx.succ, gfx.pred) for _ in repeats]

    return [
        (
            "DG adj/succ/pred x500 [property/cached]",
            property_triple,
            cached_triple,
        ),
        (
            "DG adj/succ/pred x500 [nx/fnx]",
            lambda: [(gnx.adj, gnx.succ, gnx.pred) for _ in repeats],
            cached_triple,
        ),
        (
            "len(DG.adj) x500 [nx/fnx]",
            lambda: [len(gnx.adj) for _ in repeats],
            lambda: [len(gfx.adj) for _ in repeats],
        ),
        (
            "len(DG.succ) x500 [nx/fnx]",
            lambda: [len(gnx.succ) for _ in repeats],
            lambda: [len(gfx.succ) for _ in repeats],
        ),
        (
            "len(DG.pred) x500 [nx/fnx]",
            lambda: [len(gnx.pred) for _ in repeats],
            lambda: [len(gfx.pred) for _ in repeats],
        ),
    ]


def suite_multidigraph_descriptors():
    """br-r37-c1-a5xrj: cache multi-directed public adjacency descriptors."""
    import random

    import networkx as nx
    import franken_networkx as fnx

    rng = random.Random(29)
    nodes = [str(index) for index in range(2000)]
    edges = []
    for index in range(8000):
        source = nodes[rng.randrange(len(nodes))]
        target = nodes[rng.randrange(len(nodes))]
        edges.append(
            (
                source,
                target,
                f"k{index % 3}",
                {"weight": rng.randrange(1, 21)},
            )
        )
    gnx = nx.MultiDiGraph()
    gfx = fnx.MultiDiGraph()
    for graph in (gnx, gfx):
        graph.add_nodes_from(nodes)
        graph.add_edges_from(
            (source, target, key, dict(attrs))
            for source, target, key, attrs in edges
        )
    assert type(gnx).__module__.startswith("networkx")

    repeats = range(500)
    present = nodes[:512]
    properties = fnx._MULTIDIGRAPH_PUBLIC_ADJ_PROPERTIES
    assert all(
        isinstance(fnx.MultiDiGraph.__dict__[name], fnx._CachedViewDescriptor)
        for name in ("adj", "succ", "pred")
    )
    _ = gfx.adj, gfx.succ, gfx.pred

    def property_triple():
        return [
            (
                properties["adj"].__get__(gfx, fnx.MultiDiGraph),
                properties["succ"].__get__(gfx, fnx.MultiDiGraph),
                properties["pred"].__get__(gfx, fnx.MultiDiGraph),
            )
            for _ in repeats
        ]

    def cached_triple():
        return [(gfx.adj, gfx.succ, gfx.pred) for _ in repeats]

    warm_deadline = perf_counter() + 2.0
    while perf_counter() < warm_deadline:
        property_triple()
        cached_triple()

    return [
        (
            "MDG adj/succ/pred x500 [property/cached]",
            property_triple,
            cached_triple,
        ),
        (
            "MDG adj/succ/pred x500 [nx/fnx]",
            lambda: [(gnx.adj, gnx.succ, gnx.pred) for _ in repeats],
            cached_triple,
        ),
        (
            "n in MDG.adj x512 [nx/fnx]",
            lambda: sum(node in gnx.adj for node in present),
            lambda: sum(node in gfx.adj for node in present),
        ),
        (
            "n in MDG.succ x512 [nx/fnx]",
            lambda: sum(node in gnx.succ for node in present),
            lambda: sum(node in gfx.succ for node in present),
        ),
        (
            "n in MDG.pred x512 [nx/fnx]",
            lambda: sum(node in gnx.pred for node in present),
            lambda: sum(node in gfx.pred for node in present),
        ),
        (
            "len(MDG.adj) x500 [nx/fnx]",
            lambda: [len(gnx.adj) for _ in repeats],
            lambda: [len(gfx.adj) for _ in repeats],
        ),
        (
            "len(MDG.succ) x500 [nx/fnx]",
            lambda: [len(gnx.succ) for _ in repeats],
            lambda: [len(gfx.succ) for _ in repeats],
        ),
        (
            "len(MDG.pred) x500 [nx/fnx]",
            lambda: [len(gnx.pred) for _ in repeats],
            lambda: [len(gfx.pred) for _ in repeats],
        ),
    ]


def suite_node_primitives():
    """br-r37-c1-qmi5w: raw-descriptor and competitive primitive proof."""
    import franken_networkx as fnx

    gnx, gfx = _build_pair(2000, 8000, seed=7, weighted=False)
    present = [str(i) for i in range(512)]
    missing = [f"missing-{i}" for i in range(512)]

    wrapped_has_node = fnx._private_aware_has_node(
        fnx._GRAPH_PRIVATE_AWARE_HAS_NODE
    ).__get__(gfx, type(gfx))
    wrapped_number_of_nodes = fnx._private_aware_number_of_nodes(
        fnx._GRAPH_PRIVATE_AWARE_NUMBER_OF_NODES
    ).__get__(gfx, type(gfx))

    return [
        (
            "G.has_node(present) x512 [nx/fnx]",
            lambda: sum(gnx.has_node(node) for node in present),
            lambda: sum(gfx.has_node(node) for node in present),
        ),
        (
            "G.has_node(missing) x512 [nx/fnx]",
            lambda: sum(gnx.has_node(node) for node in missing),
            lambda: sum(gfx.has_node(node) for node in missing),
        ),
        (
            "G.has_node(present) x512 [wrapper/raw]",
            lambda: sum(wrapped_has_node(node) for node in present),
            lambda: sum(gfx.has_node(node) for node in present),
        ),
        (
            "G.number_of_nodes() x512 [nx/fnx]",
            lambda: sum(gnx.number_of_nodes() for _ in present),
            lambda: sum(gfx.number_of_nodes() for _ in present),
        ),
        (
            "G.number_of_nodes() x512 [wrapper/raw]",
            lambda: sum(wrapped_number_of_nodes() for _ in present),
            lambda: sum(gfx.number_of_nodes() for _ in present),
        ),
        (
            "G.order() x512 [nx/fnx]",
            lambda: sum(gnx.order() for _ in present),
            lambda: sum(gfx.order() for _ in present),
        ),
    ]


def suite_nodeview_getitem():
    """br-r37-c1-yere4: intern warm public keys in each live NodeView."""
    gnx, gfx = _build_pair(2000, 8000, seed=7, weighted=True)
    nx_view = gnx.nodes
    fnx_view = gfx.nodes
    raw_getitem = type(fnx_view).__getitem__
    nodes = [str(i) for i in range(512)]

    def canonical_lookup():
        # ``get`` retains the former native canonical-string path for present
        # nodes, making it a conservative control: the removed Python
        # hash/try-except wrapper is not charged to this arm.
        return [fnx_view.get(node) for node in nodes]

    def interned_lookup():
        return [raw_getitem(fnx_view, node) for node in nodes]

    # Stabilize worker frequency before the first A/A round. This is benchmark
    # setup, outside every timed region, and warms both control and candidate.
    warm_deadline = perf_counter() + 2.0
    while perf_counter() < warm_deadline:
        canonical_lookup()
        interned_lookup()

    return [
        (
            "NodeView.__getitem__ x512 [canonical/interned]",
            canonical_lookup,
            interned_lookup,
        ),
        (
            "G.nodes[n] x512 [nx/fnx]",
            lambda: [gnx.nodes[node] for node in nodes],
            lambda: [gfx.nodes[node] for node in nodes],
        ),
        (
            "sum(G.nodes[n]['weight']) x512 [nx/fnx]",
            lambda: sum(gnx.nodes[node].get("weight", 0) for node in nodes),
            lambda: sum(gfx.nodes[node].get("weight", 0) for node in nodes),
        ),
    ]


def suite_lazy_rows():
    """br-r37-c1-v9auw: live row-mirror materialization and counted mechanism."""
    import networkx as nx
    import franken_networkx as fnx

    undirected_edges = [(0, node, {"weight": node}) for node in range(1, 65)]
    gnx = nx.Graph()
    gfx = fnx.Graph()
    gnx.add_edges_from((u, v, dict(attrs)) for u, v, attrs in undirected_edges)
    gfx.add_edges_from((u, v, dict(attrs)) for u, v, attrs in undirected_edges)

    directed_edges = [
        (0, node, {"weight": node}) for node in range(1, 65)
    ] + [
        (node, 0, {"weight": -node}) for node in range(65, 129)
    ]
    dnx = nx.DiGraph()
    dfx = fnx.DiGraph()
    dnx.add_edges_from((u, v, dict(attrs)) for u, v, attrs in directed_edges)
    dfx.add_edges_from((u, v, dict(attrs)) for u, v, attrs in directed_edges)

    nx_row = gnx[0]
    fnx_row = gfx[0]
    nx_succ = dnx.succ[0]
    fnx_succ = dfx.succ[0]
    nx_pred = dnx.pred[0]
    fnx_pred = dfx.pred[0]

    # Materialize each persistent mirror before timing so both mechanism arms
    # measure the steady-state most-used call, not one-time observation cost.
    dict(fnx_row)
    dict(fnx_succ)
    dict(fnx_pred)

    nodes = tuple(fnx_row)
    live = fnx_row._fnx_live_keydict
    baseline_revision = (gfx.nodes_seq, gfx.edges_seq)

    def token_checked_copy():
        # Exact counted mechanism removed by the lever: the old __getitem__
        # fetched both counters and compared this tuple for every neighbor.
        return {
            node: live[node]
            if baseline_revision == (gfx.nodes_seq, gfx.edges_seq)
            else fnx_row[node]
            for node in nodes
        }

    def live_mirror_copy():
        return {node: live[node] for node in nodes}

    return [
        (
            "dict(G[u]) degree=64 [nx/fnx]",
            lambda: dict(nx_row),
            lambda: dict(fnx_row),
        ),
        (
            "list(G[u].keys()) degree=64 [nx/fnx]",
            lambda: list(nx_row.keys()),
            lambda: list(fnx_row.keys()),
        ),
        (
            "dict(DG.succ[u]) degree=64 [nx/fnx]",
            lambda: dict(nx_succ),
            lambda: dict(fnx_succ),
        ),
        (
            "dict(DG.pred[u]) degree=64 [nx/fnx]",
            lambda: dict(nx_pred),
            lambda: dict(fnx_pred),
        ),
        (
            "row-copy loop degree=64 [token/live]",
            token_checked_copy,
            live_mirror_copy,
        ),
    ]


def suite_marshaling():
    """Return-shape / materialization surface."""
    import networkx as nx
    import franken_networkx as fnx

    gnx, gfx = _build_pair(2000, 8000, seed=7, weighted=True)
    src = "0"
    return [
        ("bfs_tree", lambda: nx.bfs_tree(gnx, src), lambda: fnx.bfs_tree(gfx, src)),
        ("dfs_tree", lambda: nx.dfs_tree(gnx, src), lambda: fnx.dfs_tree(gfx, src)),
        ("single_source_shortest_path",
         lambda: nx.single_source_shortest_path(gnx, src),
         lambda: fnx.single_source_shortest_path(gfx, src)),
        ("to_dict_of_lists",
         lambda: nx.to_dict_of_lists(gnx), lambda: fnx.to_dict_of_lists(gfx)),
        ("node_link_data",
         lambda: nx.node_link_data(gnx), lambda: fnx.node_link_data(gfx)),
        ("adjacency()->list",
         lambda: list(gnx.adjacency()), lambda: list(gfx.adjacency())),
    ]


SUITES = {
    "view-accessors": suite_view_accessors,
    "adj-descriptor": suite_adj_descriptor,
    "adj-len": suite_adjacency_len,
    "adj-iter": suite_adjacency_iter,
    "multi-adj-iter": suite_multi_adjacency_iter,
    "multi-adj-contains": suite_multi_adjacency_contains,
    "digraph-descriptors": suite_digraph_descriptors,
    "multidigraph-descriptors": suite_multidigraph_descriptors,
    "node-primitives": suite_node_primitives,
    "nodeview-getitem": suite_nodeview_getitem,
    "lazy-rows": suite_lazy_rows,
    "marshaling": suite_marshaling,
}


def main(argv):
    if len(argv) != 2 or argv[1] not in SUITES:
        print(f"usage: {argv[0]} {{{'|'.join(SUITES)}}}", file=sys.stderr)
        return 2
    name = argv[1]
    results = run_rows(f"suite={name}", SUITES[name]())
    losses = [r for r in results if r.get("ratio_p50", 1) < 1.0 and r.get("decidable")]
    if losses:
        print("\ndecidable losses (fnx slower):", flush=True)
        for row in sorted(losses, key=lambda r: r["ratio_p50"]):
            print(f"  {row['ratio_p50']:7.4f}x  {row['label']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
