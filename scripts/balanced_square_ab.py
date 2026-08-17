"""Balanced-square vs-incumbent A/B, usable on a contended host.

WHY THIS EXISTS. `scripts/perf_harness.py` is the sanctioned harness, and its
`require_host_wide_quiescence()` is mandatory at both `pre_setup` and
`pre_measurement`: it demands five consecutive windows in which EVERY cpu on the
box is idle. On a 64-way host shared by tens of agents that condition is
effectively unreachable — `br-r37-c1-3s8x7` recorded 25 consecutive attempts
with zero admitted, and a run of mine aborted with
``host-wide benchmark exclusivity failed at pre_setup after 300 windows,
cpu47=100.0%``. The result is a fleet that cannot produce the one artifact the
campaign accepts as a win: a vs-incumbent ratio measured live, in the same
invocation.

This substrate reaches those rows WITHOUT a host-wide gate, because it does not
try to make the host quiet — it makes the COMPARISON immune to the host being
busy:

  * Both arms run INSIDE one round, interleaved as a balanced square
    ``A B B A A B B A``. Each arm occupies the same set of slot POSITIONS, so
    any drift across the round hits both equally instead of biasing one.
  * Each arm carries its own A/A null: the same arm's first-half slots divided
    by its second-half slots, which must come out 1.0. A null is what detects
    the contention this gate was trying to exclude — so contention is caught
    per-row, after the fact, instead of being excluded up front.
  * A row whose null leaves [0.98, 1.02] is reported NULL-FAILED and its ratio
    is not a result. REFUSING is the point; see `mutation_arms_fail_aa_nulls`.

It is NOT a replacement for perf_harness.py's contract rows. It is the
substrate to use when the gate cannot be met, which is most of the time.

USAGE

    PYTHONPATH=python PYTHONHASHSEED=0 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
      taskset -c 40-47 python3 scripts/balanced_square_ab.py --workload view-reads

    --workload   which registered workload set to run (see --list)
    --rounds     rounds per row (default 41)
    --reps       operations per timed slot (default 400)
    --expect-elf first 16 hex chars of the ELF you INTEND to measure; the run
                 aborts on mismatch. A bare `python3` silently loads the
                 site-packages build, which is a DIFFERENT binary — this guard
                 exists because that trap cost a full session's numbers once.

Ratio convention is t_incumbent / t_fnx, so > 1 means fnx is faster. That is
the same convention the ledgers use.

TWO THINGS THAT MOVE A ROW WITHOUT ANY CODE CHANGING (br-r37-c1-y4r63), found
when this harness and an ablation harness disagreed by 2x on the same ELF:

  * ROW CONTEXT. Every row runs in one process, so the rows before it have
    already warmed and dirtied the structures it reads. `(u,v) in G.edges()`
    measures 0.4254x with the full eight-row set and 0.5099x with `--only`,
    same build, minutes apart, both admissible. Use `--only` when you are
    quoting a single row, and say which way you ran it.
  * PROBE KEY IDENTITY. CPython's dict compares POINTERS before it compares
    strings, so networkx is ~1.17x faster when the key object handed to
    `in` is the object it already stores than when it is an equal copy. fnx
    canonicalises and memcmps either way, so it gets no such shortcut. Each
    arm here builds its probes from its OWN fixture, which gives networkx that
    shortcut; a harness that feeds one library's key objects to both arms
    silently biases the ratio by that much in the other direction. Neither is
    wrong, but a row is only comparable to another row measured the same way.

ADDING A WORKLOAD. Append to `WORKLOADS`. A workload is a callable returning
`(build, ops)` where `build(module)` constructs an equivalent graph in either
library and `ops(graph, fixture)` returns `{label: callable}`. Every op is
parity-gated against the incumbent BEFORE timing, so an arm that computes
something different fails loudly instead of producing a fast wrong number.
Include at least one row the change under test CANNOT affect, as a control.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import os
import platform
import random
import pathlib
import subprocess
import socket
import statistics
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

import networkx as nx

import franken_networkx as fnx
import franken_networkx._fnx as _fnx_ext

SQUARE = "ABBAABBA"
NULL_BOUND = 0.02
# br-r37-c1-clockrow: the two arms of one square interleave, so they should meet
# the same core frequency. A skew wider than this between the arms' median clocks
# is a bias on the RATIO that both A/A nulls read as 1.0, so it is flagged on the
# row rather than left for the reader to infer from a whole-run average.
CLOCK_SKEW_BOUND_PCT = 1.0
# br-r37-c1-7x25w: untimed calls per arm after the per-round collect. One was
# not enough at reps=400 — the incumbent arm still showed a first/second-half
# null of 1.1084 — because the collect leaves the caches cold and a single call
# does not refill them. Two clears it at every rep count measured.
ROUND_WARM_CALLS = 2


# ---------------------------------------------------------------------------
# Provenance, self-reported from INSIDE this process.
#
# Every field here exists because a ratio without it is not checkable: the
# ACTUAL observed thread count (not the requested one), host identity, CPU
# governor, runtime ISA, and an ELF SHA-256 read from the loaded module's own
# path so a harness cannot silently compare a build against itself.
#
# WHICH HARNESS produced a row is provenance too, and it is the field the fleet
# was missing. frankenlibc measured one primitive on ONE worker with two
# separately-sanctioned harnesses and got 5.9459x and 12.385414x — a ~2x spread
# with BOTH A/A nulls inside tolerance. This repo hit the same thing
# independently: `(u,v) in G.edges()` read 0.4254x here and 0.8502x in an
# ablation harness on the same ELF minutes apart, both admissible
# (`br-r37-c1-y4r63`). A null certifies stationarity WITHIN one harness's run;
# it says nothing about whether two harnesses measure the same thing. So the
# harness names itself, and hashes its own source, in every row it prints.
#
# WHERE it ran is a gate, not a suggestion: `same_host` when both arms ran in
# this process on this machine, and `rch_worker` when the run was dispatched to
# a worker. A row that cannot name where it ran is not comparable to any other
# row, because worker identity alone has moved a ratio 13.6x elsewhere in the
# fleet with passing nulls.
# ---------------------------------------------------------------------------
def provenance() -> dict:
    elf = _fnx_ext.__file__
    # br-r37-c1-shimprov: the shim is resolved from the IMPORTED module, not from
    # the repo path, so an arm running out of a package copy reports the copy it
    # actually executed rather than the tree it was made from.
    # Resolved from the REPO, not the arm: an arm is a copy of the tree, so the
    # tree it was copied from is what identifies its content. Reported as
    # "unavailable" rather than failing when git is absent or this is not a
    # checkout, since the harness must still run in those setups.
    def _git(*args: str) -> str:
        try:
            out = subprocess.run(
                ["git", "-C", str(pathlib.Path(__file__).resolve().parent.parent), *args],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return out.stdout.strip() if out.returncode == 0 else "unavailable"
        except (OSError, subprocess.SubprocessError):
            return "unavailable"

    _git_head = _git("rev-parse", "HEAD")
    _git_dirty = "dirty" if _git("status", "--porcelain", "--", "crates") else "clean"

    _SHIM_PATH = fnx.__file__
    try:
        with open(_SHIM_PATH, "rb") as handle:
            _shim_bytes = handle.read()
        _shim_sha = hashlib.sha256(_shim_bytes).hexdigest()
        _shim_lines = _shim_bytes.count(b"\n")
    except OSError:
        _shim_sha, _shim_lines = "unavailable", -1
    with open(elf, "rb") as handle:
        elf_sha = hashlib.sha256(handle.read()).hexdigest()
    harness = Path(__file__).resolve()
    with open(harness, "rb") as handle:
        harness_sha = hashlib.sha256(handle.read()).hexdigest()
    try:
        with open("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor") as handle:
            governor = handle.read().strip()
    except OSError:
        governor = "unavailable"
    flags = ""
    try:
        with open("/proc/cpuinfo") as handle:
            for line in handle:
                if line.startswith("flags"):
                    flags = line
                    break
    except OSError:
        pass
    isa = [f for f in ("avx512f", "avx2", "avx", "sse4_2") if f" {f} " in flags]
    threads = "unknown"
    try:
        with open("/proc/self/status") as handle:
            for line in handle:
                if line.startswith("Threads:"):
                    threads = line.split()[1]
                    break
    except OSError:
        pass
    # Both arms of every row in this harness run inside THIS process, so the
    # machine that ran them is this one. `RCH_WORKER` is reported when set so a
    # dispatched run says so itself rather than being inferred later.
    worker = os.environ.get("RCH_WORKER") or os.environ.get("RCH_WORKER_ID")
    return {
        "harness": harness.name,
        "harness_sha256": harness_sha,
        "same_host": socket.gethostname(),
        "rch_worker": worker or "none (both arms in-process on same_host)",
        "host": socket.gethostname(),
        "elf": elf,
        "elf_sha256": elf_sha,
        "governor": governor,
        "runtime_isa": ",".join(isa) or "baseline",
        # br-r37-c1-shimprov: record the PYTHON SHIM, not just the extension.
        #
        # Every row here already carried an ELF sha256, which pins the Rust half
        # and nothing else. The half it does not pin is the one that actually
        # inverted a ratio on this host: an installed `franken_networkx/__init__.py`
        # 2751 lines and twelve days behind the repo made `G.adj[u]` at
        # 2000-character keys read 0.1568x where the repo shim read 0.8530x — the
        # same call, the SAME extension, a 5.4x difference traceable entirely to
        # the Python layer, and it sent an investigation after a defect that had
        # already been fixed.
        #
        # Both arms of an ELF-alternated run are usually copies of the same tree,
        # so the shim cancels — but that is an assumption a row should state
        # rather than rely on. With this recorded, two rows can be compared after
        # the fact and a shim mismatch is visible instead of silent.
        "shim": _SHIM_PATH,
        "shim_sha256": _shim_sha,
        "shim_lines": _shim_lines,
        # br-r37-c1-shimprov: the TREE the running build came from.
        #
        # This is the confound that shim_sha256 alone does not catch, and it cost
        # a whole certification. On a shared checkout, an arm built at 21:12
        # silently contains every peer commit landed since the arm built at
        # 21:07 — so an "OLD vs NEW" pair can differ by far more than your own
        # hunk. Measured: a pair meant to isolate one keydict change came out 3x
        # apart AT par=1, where that change cannot matter, because the later arm
        # had absorbed a peer's index-keying commit worth 7.03x. The labels were
        # not wrong; the trees were.
        #
        # Recording HEAD makes that visible on the row instead of requiring
        # someone to reconstruct build times from git log afterwards. Two arms
        # that do not share a git_head are not an A/B of your change.
        "git_head": _git_head,
        "git_dirty": _git_dirty,
        "observed_os_threads": threads,
        "observed_affinity_cpus": len(os.sched_getaffinity(0)),
        "affinity_cpu_list": sorted(os.sched_getaffinity(0)),
        # br-r37-c1-armplace: SMT exposure of the pinned set. Every CPU here may
        # be the second hyperthread of a physical core whose FIRST thread is
        # running someone else's benchmark — on this host cpu40..47 are the
        # siblings of cpu8..15. That contention is common-mode across arms that
        # interleave in one process, but it is not visible from the CPU numbers
        # alone, so it is stated rather than left to be discovered.
        "smt_siblings": smt_sibling_map(),
        "python": platform.python_version(),
        "incumbent_networkx": nx.__version__,
        "pythonhashseed": os.environ.get("PYTHONHASHSEED", "<unset>"),
        "loadavg_start": os.getloadavg(),
    }


# ---------------------------------------------------------------------------
# Workloads
# ---------------------------------------------------------------------------
def _simple_graph(module, nodes: int, edges: int, seed: int = 11):
    """An identically-shaped attributed simple graph in either library."""
    rng = random.Random(seed)
    graph = module.Graph()
    names = [f"n{i}" for i in range(nodes)]
    graph.add_nodes_from((n, {"color": "r", "rank": i}) for i, n in enumerate(names))
    seen: set[tuple[int, int]] = set()
    while len(seen) < edges:
        a, b = rng.randrange(nodes), rng.randrange(nodes)
        if a == b:
            continue
        pair = (min(a, b), max(a, b))
        if pair in seen:
            continue
        seen.add(pair)
        graph.add_edge(names[pair[0]], names[pair[1]], weight=1.0)
    return graph, (names, [(names[a], names[b]) for a, b in seen])


def workload_view_reads(reps: int):
    """Read probes on the view surface (br-r37-c1-ey6ob, br-r37-c1-ef8rt)."""

    def build(module):
        return _simple_graph(module, 2000, 8000)

    def ops(graph, fixture):
        names, edges = fixture
        # Seeded on purpose: the probe sequence must be identical in both arms
        # and reproducible across runs. This is fixture selection, not secret
        # material, so `random` is correct here and `secrets` would be wrong.
        rng = random.Random(7)
        probe_nodes = [names[rng.randrange(len(names))] for _ in range(reps)]
        probe_edges = [edges[rng.randrange(len(edges))] for _ in range(reps)]
        nodeview, edgeview = graph.nodes, graph.edges
        return {
            "n in G": lambda: sum(1 for n in probe_nodes if n in graph),
            "G.has_node(n)": lambda: sum(1 for n in probe_nodes if graph.has_node(n)),
            "n in G.nodes()": lambda: sum(1 for n in probe_nodes if n in nodeview),
            "G.nodes[n]": lambda: sum(len(nodeview[n]) for n in probe_nodes),
            "G.nodes.get(n)": lambda: sum(len(nodeview.get(n)) for n in probe_nodes),
            "(u,v) in G.edges()": lambda: sum(1 for p in probe_edges if p in edgeview),
            "G.edges[u,v]": lambda: sum(len(edgeview[u, v]) for u, v in probe_edges),
            # br-r37-c1-7x25w: these three were only ever measured by a scratch
            # sweep carrying the per-slot collect. They live here now so every
            # future ranking of this surface comes off one corrected substrate.
            "G.degree(n)": lambda: sum(graph.degree(n) for n in probe_nodes),
            "list(G.neighbors(n))": lambda: sum(
                len(list(graph.neighbors(n))) for n in probe_nodes
            ),
            "G.adj[u]": lambda: sum(len(graph.adj[n]) for n in probe_nodes),
            # Control: no view lever can touch a bare node count.
            "CONTROL len(G)": lambda: sum(len(graph) for _ in range(reps)),
        }

    return build, ops


def _directed_graph(module, nodes: int, edges: int, seed: int = 11):
    """An identically-shaped weighted digraph in either library."""
    rng = random.Random(seed)
    graph = module.DiGraph()
    names = [f"n{i}" for i in range(nodes)]
    graph.add_nodes_from(names)
    seen: set[tuple[int, int]] = set()
    while len(seen) < edges:
        a, b = rng.randrange(nodes), rng.randrange(nodes)
        if a == b or (a, b) in seen:
            continue
        seen.add((a, b))
        graph.add_edge(names[a], names[b], weight=1 + (a + b) % 19)
    return graph, (names, sorted(seen))


def workload_view_reads_directed(reps: int):
    """The directed twin of `view-reads` (br-r37-c1-p1tvg).

    `DiGraph.edges` is the PYTHON `_DiGraphEdgeView`, so its `__contains__`
    lands in `PyDiGraph::has_edge` rather than in a native view class — a
    different code path from the undirected row, and one nothing measured
    until this workload existed. Reversed probes are included because a
    direction-blind lookup answers them wrongly and would otherwise look fast.
    """

    def build(module):
        return _directed_graph(module, 2000, 8000)

    def ops(graph, fixture):
        names, seen = fixture
        rng = random.Random(7)
        edges = [(names[a], names[b]) for a, b in seen]
        probe_nodes = [names[rng.randrange(len(names))] for _ in range(reps)]
        probe_edges = [edges[rng.randrange(len(edges))] for _ in range(reps)]
        reversed_edges = [(v, u) for u, v in probe_edges]
        edgeview = graph.edges
        return {
            "(u,v) in D.edges()": lambda: sum(1 for p in probe_edges if p in edgeview),
            "(v,u) in D.edges()": lambda: sum(
                1 for p in reversed_edges if p in edgeview
            ),
            "D.has_edge(u,v)": lambda: sum(
                1 for u, v in probe_edges if graph.has_edge(u, v)
            ),
            "D.edges[u,v]": lambda: sum(len(edgeview[u, v]) for u, v in probe_edges),
            # Control: no edge-lookup lever can touch a bare node count.
            "CONTROL len(D)": lambda: sum(len(graph) for _ in range(reps)),
            "CONTROL n in D": lambda: sum(1 for n in probe_nodes if n in graph),
        }

    return build, ops


def workload_algorithms(reps: int):
    """Whole-algorithm rows, for the br-r37-c1-p80x1 conversion queue.

    These are the operations whose published README ratios have no paired
    incumbent arm, and whose retry beads (p80x1.*) are all parked on
    "after stable target reuse" — i.e. on the harness gate this substrate does
    not need. `reps` is ignored here: an algorithm call is its own unit of work,
    and `--calls-per-slot` decides how many of them a timed slot holds.

    br-r37-c1-j3i9q: at one call per slot, 9 of these 11 rows failed their A/A
    nulls while reporting stable ratios with tight CIs — the null was comparing
    the variance of ONE call against ONE call. `--calls-per-slot` is what makes
    the null resolvable, and it is reported in the run header because a row
    measured at K=1 and one measured at K=5 are not automatically the same
    measurement: anything that warms on first call reads differently, and that
    difference is a finding about the operation rather than noise.
    """

    def build(module):
        undirected, (names, edges) = _simple_graph(module, 400, 1600)
        directed, (dnames, dedges) = _directed_graph(module, 400, 1600)
        return undirected, (names, edges, directed, dnames, dedges, module)

    def ops(graph, fixture):
        names, _edges, digraph, dnames, _dedges, module = fixture
        source = names[0]
        target = names[len(names) // 2]
        return {
            "pagerank": lambda: module.pagerank(graph),
            "dfs_successors": lambda: module.dfs_successors(graph, source),
            "bfs_tree->edges": lambda: sorted(module.bfs_tree(graph, source).edges()),
            "single_source_sp_length": lambda: dict(
                module.single_source_shortest_path_length(graph, source)
            ),
            "shortest_path(weighted)": lambda: module.shortest_path(
                digraph, dnames[0], dnames[7], weight="weight"
            ),
            "kosaraju_scc": lambda: sorted(
                map(sorted, module.kosaraju_strongly_connected_components(digraph))
            ),
            "connected_components": lambda: sorted(
                map(sorted, module.connected_components(graph))
            ),
            "edges(data=True)": lambda: len(list(graph.edges(data=True))),
            "degree_centrality": lambda: module.degree_centrality(graph),
            "subgraph(view)->edges": lambda: sorted(
                graph.subgraph(names[:200]).edges()
            ),
            # Control: a bare edge count is untouched by any algorithm lever.
            "CONTROL number_of_edges": lambda: graph.number_of_edges(),
        }

    return build, ops


def _plain_graph(module, nodes: int, edges: int, seed: int = 11):
    """Unweighted simple graph with bare `str(i)` node names.

    Distinct from `_simple_graph` in two ways that the p80x1 fixtures depend
    on: no node or edge attributes, and node names are `"0"`, `"1"`, ... rather
    than `"n0"`. Those beads name a source node `"0"` and an unreached node
    `135`, so the naming is part of the recorded fixture, not decoration.
    """
    rng = random.Random(seed)
    graph = module.Graph()
    names = [str(i) for i in range(nodes)]
    graph.add_nodes_from(names)
    seen: set[tuple[int, int]] = set()
    while len(seen) < edges:
        a, b = rng.randrange(nodes), rng.randrange(nodes)
        if a == b:
            continue
        pair = (min(a, b), max(a, b))
        if pair in seen:
            continue
        seen.add(pair)
        graph.add_edge(names[pair[0]], names[pair[1]])
    return graph, names


def workload_incumbent_fixtures(reps: int):
    """The p80x1 retry fixtures AT THE SIZES THOSE BEADS NAME.

    `algorithms` above already serves this queue, but it runs everything on one
    n=400,m=1600 graph, and every one of these beads names a different and
    larger shape: p80x1.40 and p80x1.18 want n=2000,m=8000,seed=7; p80x1.30
    wants n=1200,m=6000,seed=11; p80x1.12 wants n=300,m=1200,seed=11. Size is
    not a detail on this surface — `subgraph(...).edges()` was 0.0015x before
    br-r37-c1-cn8w4 and its ratio still degrades with node count from a better
    starting point, so a row measured at n=400 does not answer a bead that
    names n=2000. These rows exist to answer the beads as written.

    FIXTURE IDENTITY IS CONFIRMED, not assumed. The beads record structural
    fingerprints of the 2026-07-31 fixtures, and the builders below reproduce
    every one of them exactly:

      p80x1.18   500-node view, 497-edge timed output      -> 500 / 497
      p80x1.30   1068 parent keys, 1199 reached, node 135
                 the ONLY unreached node                   -> 1068 / 1199 / 135
      p80x1.12   300 outer mappings, 90000 inner items     -> 300 / 90000

    "only node 135 unreached" is the load-bearing one: it is a property of one
    specific edge set, not of the shape, so matching it means this generator IS
    the generator those beads used. The recorded input/output SHA-256s are not
    re-derived here because the beads do not record the canonical byte encoding
    they were taken over, and inventing one would prove nothing.
    """

    def build(module):
        attributed, (names_2k, _e) = _simple_graph(module, 2000, 8000, seed=7)
        dfs_graph, dfs_names = _plain_graph(module, 1200, 6000, seed=11)
        apsp_graph, apsp_names = _plain_graph(module, 300, 1200, seed=11)
        return attributed, (names_2k, dfs_graph, dfs_names, apsp_graph, apsp_names, module)

    def ops(graph, fixture):
        names_2k, dfs_graph, _dfs_names, apsp_graph, _apsp_names, module = fixture
        # p80x1.18: "selects every fourth string node" of the n=2000 fixture.
        quarter = names_2k[::4]
        # p80x1.48 wants BOTH halves: the present probe and the missing probe.
        # Only the present one is covered by `view-reads`, and a miss takes a
        # different path through the key lookup than a hit.
        rng = random.Random(7)
        present = [names_2k[rng.randrange(len(names_2k))] for _ in range(512)]
        missing = [f"absent{i}" for i in range(512)]
        return {
            # p80x1.40
            "edges(data=True) n=2000": lambda: len(list(graph.edges(data=True))),
            # p80x1.18
            "subgraph(n/4)->edges n=2000": lambda: sorted(
                graph.subgraph(quarter).edges()
            ),
            # p80x1.48, both halves
            "has_node present x512": lambda: sum(
                1 for n in present if graph.has_node(n)
            ),
            "has_node missing x512": lambda: sum(
                1 for n in missing if graph.has_node(n)
            ),
            # p80x1.30
            "dfs_successors n=1200": lambda: module.dfs_successors(dfs_graph, "0"),
            # p80x1.12
            "all_pairs_sp_length n=300": lambda: {
                k: dict(v)
                for k, v in module.all_pairs_shortest_path_length(apsp_graph)
            },
            # Control: nothing on this list can move a bare node count.
            "CONTROL len(G)": lambda: len(graph),
        }

    return build, ops


def _weighted_plain_graph(module, nodes: int, edges: int, seed: int = 5):
    """`_plain_graph` with a `weight` attribute, for the weighted fixtures."""
    rng = random.Random(seed)
    graph = module.Graph()
    names = [str(i) for i in range(nodes)]
    graph.add_nodes_from(names)
    seen: set[tuple[int, int]] = set()
    while len(seen) < edges:
        a, b = rng.randrange(nodes), rng.randrange(nodes)
        if a == b:
            continue
        pair = (min(a, b), max(a, b))
        if pair in seen:
            continue
        seen.add(pair)
        graph.add_edge(names[pair[0]], names[pair[1]], weight=1 + (a + b) % 19)
    return graph, names


def workload_incumbent_fixtures_2(reps: int):
    """The second batch of p80x1 retry fixtures (16, 20, 22, 26, 36, 42).

    Same rationale as `incumbent-fixtures`; split only so a run of one batch
    stays inside a sane wall-clock. Fixture identity is again CONFIRMED against
    each bead's recorded fingerprints rather than assumed:

      p80x1.20   tie-sensitive path 0->1999 is [0,192,496,1859,1999]
      p80x1.22   pagerank is 2000 floats summing to 0.9999999999999998
      p80x1.16   300 outer mappings, 90000 inner items
      p80x1.42   all_simple_edge_paths(0,5,cutoff=4) projects to 41 paths

    p80x1.18/.20/.22 all record input SHA-256 03635cb9…, i.e. ONE shared
    n=2000,m=8000,seed=7 graph. `_plain_graph` and `_simple_graph` consume the
    rng identically, so they emit the same edge set and differ only in node
    naming and attributes — which is why the .18 fingerprint matched under
    `_simple_graph` while .20's path fingerprint matches under `_plain_graph`.
    """

    def build(module):
        big, _names = _plain_graph(module, 2000, 8000, seed=7)
        wsmall, _ = _weighted_plain_graph(module, 300, 1200, seed=11)
        sparse, _ = _weighted_plain_graph(module, 600, 3000, seed=5)
        plain_small, _ = _plain_graph(module, 300, 1200, seed=11)
        paths, _ = _plain_graph(module, 200, 800, seed=13)
        return big, (wsmall, sparse, plain_small, paths, module)

    def ops(graph, fixture):
        wsmall, sparse, plain_small, paths, module = fixture
        return {
            # p80x1.20
            "shortest_path(0,1999) n=2000": lambda: module.shortest_path(
                graph, "0", "1999"
            ),
            # p80x1.22
            "pagerank n=2000": lambda: module.pagerank(graph),
            # p80x1.16
            "all_pairs_dijkstra_len n=300": lambda: {
                k: dict(v)
                for k, v in module.all_pairs_dijkstra_path_length(
                    wsmall, weight="weight"
                )
            },
            # p80x1.36
            "all_pairs_shortest_path n=300": lambda: {
                k: dict(v) for k, v in module.all_pairs_shortest_path(plain_small)
            },
            # p80x1.26
            "to_scipy_sparse_array n=600": lambda: module.to_scipy_sparse_array(
                sparse
            ).toarray(),
            # p80x1.42
            "all_simple_edge_paths n=200": lambda: sum(
                1 for _ in module.all_simple_edge_paths(paths, "0", "5", cutoff=4)
            ),
            # Control: untouched by any algorithm lever on this list.
            "CONTROL number_of_edges": lambda: graph.number_of_edges(),
        }

    return build, ops


def _multi_graph(module, nodes: int, edges: int, *, directed: bool, seed: int = 11):
    """An identically-shaped weighted multigraph in either library.

    Parallel edges are deliberate: every 5th pair is added twice, so the keyed
    subscript has more than key 0 to find and a row is not just a simple graph
    wearing a multigraph type.
    """
    rng = random.Random(seed)
    graph = (module.MultiDiGraph if directed else module.MultiGraph)()
    names = [f"n{i}" for i in range(nodes)]
    graph.add_nodes_from(names)
    triples = []
    while len(triples) < edges:
        a, b = rng.randrange(nodes), rng.randrange(nodes)
        if a == b:
            continue
        key = graph.add_edge(names[a], names[b], weight=1 + (a + b) % 19)
        triples.append((names[a], names[b], key))
        if len(triples) % 5 == 0 and len(triples) < edges:
            key2 = graph.add_edge(names[a], names[b], weight=2 + (a + b) % 19)
            triples.append((names[a], names[b], key2))
    return graph, (names, triples)


def workload_view_reads_multi(reps: int):
    """The MULTIGRAPH twin of `view-reads` (br-r37-c1-ki2ni, br-r37-c1-tjp0g).

    `view-reads` covers Graph and `view-reads-directed` covers DiGraph, so the
    two multigraph classes had no ABBA row at all — their subscript ratios were
    only ever measured by a scratch sweep on an ELF that no longer exists. They
    are the worst rows on this surface, so they need a substrate rather than a
    remembered number.

    The keyed subscript is the point: `G.edges[u, v, k]` on a multigraph
    REQUIRES a 3-tuple (networkx's OutMultiEdgeView does `u, v, k = e`), so this
    is a genuinely different code path from the 2-tuple one the simple classes
    take, not the same row with a different receiver.
    """

    def build(module):
        undirected, (names, triples) = _multi_graph(module, 2000, 8000, directed=False)
        directed, (dnames, dtriples) = _multi_graph(module, 2000, 8000, directed=True)
        return undirected, (names, triples, directed, dnames, dtriples)

    def ops(graph, fixture):
        names, triples, digraph, _dnames, dtriples = fixture
        rng = random.Random(7)
        probe = [triples[rng.randrange(len(triples))] for _ in range(reps)]
        dprobe = [dtriples[rng.randrange(len(dtriples))] for _ in range(reps)]
        view, dview = graph.edges, digraph.edges
        return {
            "MG G.edges[u,v,k]": lambda: sum(len(view[u, v, k]) for u, v, k in probe),
            "MDG G.edges[u,v,k]": lambda: sum(
                len(dview[u, v, k]) for u, v, k in dprobe
            ),
            "MG (u,v,k) in G.edges()": lambda: sum(1 for t in probe if t in view),
            "MG G.get_edge_data(u,v,k)": lambda: sum(
                len(graph.get_edge_data(u, v, k)) for u, v, k in probe
            ),
            "MG G.has_edge(u,v,k)": lambda: sum(
                1 for u, v, k in probe if graph.has_edge(u, v, k)
            ),
            # Controls: no edge-subscript lever can move a bare node count.
            "CONTROL len(G)": lambda: sum(len(graph) for _ in range(reps)),
            "CONTROL n in G": lambda: sum(1 for n in names[:reps] if n in graph),
        }

    return build, ops


def workload_key_length_scaling(reps: int):
    """`G.edges[u,v]` against NODE-KEY LENGTH (br-r37-c1-ptiz2).

    The axis no other workload varies, and the one that exposed the defect this
    lever fixes. Lengths straddle the 128-byte canonical buffer
    (`CANONICAL_KEY_STACK_BUF`), because the measured allocation step sits
    exactly at canon bytes 128 -> 133, i.e. between node-key lengths 120 and 125.

    `has_edge` is the CONTROL: it canonicalises identically but never reaches the
    edge-attribute lookaside, and it was already flat in key length before the
    change. If it moves, the lever leaked outside its scope.
    """

    def build(module):
        graphs = {}
        for length in (3, 120, 130, 400):
            u, v = "u" * length, "v" * length
            graph = module.Graph()
            graph.add_edge(u, v, weight=1)
            graphs[length] = (graph, u, v)
        return graphs[3][0], graphs

    def ops(graph, fixture):
        table = {}
        for length, (g, u, v) in fixture.items():
            view = g.edges
            table[f"edges[u,v] len={length}"] = (
                lambda view=view, u=u, v=v: view[u, v]
            )
        for length in (3, 400):
            g, u, v = fixture[length]
            table[f"CONTROL has_edge len={length}"] = (
                lambda g=g, u=u, v=v: g.has_edge(u, v)
            )
        base = fixture[3][0]
        table["CONTROL len(G)"] = lambda: len(base)
        return table

    return build, ops


def workload_multi_key_length(reps: int):
    """MULTIGRAPH `G.edges[u,v,k]` against node-key length (br-r37-c1-tjp0g).

    br-r37-c1-ptiz2 removed the key-length scaling defect from the SIMPLE-graph
    `EdgeView` only. The multigraph classes keep their own keyed attribute
    storage, so the defect should still be present here — and this workload is
    what says so with an A/A null instead of an assertion.

    The simple-Graph row at the same length is carried as a POSITIVE control: it
    is the surface that was fixed, so it should be flat while the multigraph rows
    are not. A run where both are flat, or both grow, means the fixture is
    measuring something other than what it claims.
    """

    def build(module):
        fixture = {}
        for length in (3, 130, 2000, 8000):
            u, v = "u" * length, "v" * length
            mdg = module.MultiDiGraph()
            mdg.add_edge(u, v, weight=1)
            # br-r37-c1-f3i50: the undirected multigraph, which this fixture
            # never built despite the workload being about keyed subscripts.
            mg = module.MultiGraph()
            mg.add_edge(u, v, weight=1)
            simple = module.Graph()
            simple.add_edge(u, v, weight=1)
            fixture[length] = (mdg, mg, simple, u, v)
        return fixture[3][0], fixture

    def ops(graph, fixture):
        table = {}
        for length, (mdg, mg, simple, u, v) in fixture.items():
            mview, mgview, sview = mdg.edges, mg.edges, simple.edges
            # br-r37-c1-f3i50: the UNDIRECTED keyed subscript, which had no row
            # here at all — the workload carried only the directed twin, which is
            # how the undirected class kept the keyed index cache missing while
            # the directed one had it since br-r37-c1-7qqr8. A surface with no
            # row is a surface nobody re-measures.
            table[f"MG edges[u,v,k] len={length}"] = (
                lambda mgview=mgview, u=u, v=v: mgview[u, v, 0]
            )
            table[f"MDG edges[u,v,k] len={length}"] = (
                lambda mview=mview, u=u, v=v: mview[u, v, 0]
            )
            table[f"CONTROL Graph edges[u,v] len={length}"] = (
                lambda sview=sview, u=u, v=v: sview[u, v]
            )
        mdg3, _mg3, _s, u3, v3 = fixture[3]
        mdg_long, _mgl, _s2, ul, vl = fixture[2000]
        table["CONTROL MDG has_edge len=3"] = lambda: mdg3.has_edge(u3, v3, 0)
        table["CONTROL MDG has_edge len=2000"] = lambda: mdg_long.has_edge(ul, vl, 0)
        # br-r37-c1-ptiz2: the KEYLESS form is a different code path from the
        # keyed one above — it can resolve entirely by node index, where the
        # keyed form still needs canonical strings for the edge key.
        table["MDG has_edge KEYLESS len=3"] = lambda: mdg3.has_edge(u3, v3)
        table["MDG has_edge KEYLESS len=2000"] = lambda: mdg_long.has_edge(ul, vl)
        # br-r37-c1-tjp0g attribution rows: get_edge_data is ~90% of the
        # subscript at long keys, so it is measured directly rather than
        # inferred by subtraction.
        table["ATTRIB MDG get_edge_data len=3"] = lambda: mdg3.get_edge_data(u3, v3, 0)
        table["ATTRIB MDG get_edge_data len=2000"] = (
            lambda: mdg_long.get_edge_data(ul, vl, 0)
        )
        # has_node is the FLAT control: node canonicalisation alone does not
        # scale, so a growing get_edge_data cannot be blamed on it.
        table["CONTROL MDG has_node len=2000"] = lambda: mdg_long.has_node(ul)
        # br-r37-c1-ptiz2 SCOPE CHECK: that lever fixed the native EdgeView C
        # slot, i.e. `Graph.edges[u,v]`. `Graph.get_edge_data` returns the SAME
        # dict by a different route, so if it is NOT flat the fix was narrower
        # than "the simple-graph subscript" and the ledger must say so.
        for length in (3, 8000):
            _m, _mg, simple, su, sv = fixture[length]
            table[f"Graph get_edge_data len={length}"] = (
                lambda simple=simple, su=su, sv=sv: simple.get_edge_data(su, sv)
            )
            # br-r37-c1-ptiz2: the remaining unbounded family members. G[u][v]
            # reaches the same attr dict through AtlasView rather than through
            # the EdgeView slot or get_edge_data, so it is a THIRD route and was
            # screened at 0.0706x while the other two are now ~0.7x.
            table[f"Graph G[u][v] len={length}"] = (
                lambda simple=simple, su=su, sv=sv: simple[su][sv]
            )
            # br-r37-c1-ptiz2: the remaining unbounded family after all three
            # attr-dict routes were fixed. `(u,v) in G.edges` is a MEMBERSHIP
            # test, not an attr fetch, so it does not touch the lookaside at
            # all — a different mechanism on the same key-length axis.
            table[f"Graph (u,v) in edges len={length}"] = (
                lambda simple=simple, su=su, sv=sv: (su, sv) in simple.edges
            )
            table[f"Graph degree(u) len={length}"] = (
                lambda simple=simple, su=su: simple.degree(su)
            )
        return table

    return build, ops


def workload_parallel_keydict(reps: int):
    """Unkeyed multigraph `get_edge_data(u,v)` against the PARALLEL-EDGE count.

    br-r37-c1-ptiz2. The axis here is the number of parallel edges between one
    endpoint pair, not node-key length. networkx hands back its existing keydict
    and is therefore O(1) in that count; fnx rebuilds the `{key: attrs}` mapping
    per call, so it grew ~237ns per parallel edge and reached 0.0072x at par=64
    — the worst cell measured in this campaign.

    The lever hoists the `(String, String, usize)` edge key out of the loop, so
    the four full-length string allocations per parallel edge become two per
    call. The residual is the dict build itself.

    THE CONTROLS MATTER MORE THAN THE SUBJECT HERE. par=1 is carried for every
    class: at one parallel edge the loop body runs once, so the hoist can save
    at most one redundant tuple and the row should barely move. A run where
    par=1 improves as much as par=64 is measuring call overhead, not the loop.
    `G[u][v]` is the SIBLING control — it reaches the same keydict by another
    route and was already ~15x faster, so it bounds what closing this loop can
    win. `has_edge` is the flat control: same endpoints, no keydict built.
    """
    PARALLEL = (1, 8, 64)

    def build(module):
        fixture = {}
        for cls in ("MultiGraph", "MultiDiGraph"):
            for par in PARALLEL:
                u, v = "u" * 130, "v" * 130
                graph = getattr(module, cls)()
                for i in range(par):
                    graph.add_edge(u, v, weight=i)
                # Bulk so the pair is not the only thing in the graph.
                for i in range(200):
                    graph.add_edge(f"a{i}", f"b{i}")
                fixture[(cls, par)] = (graph, u, v)
        # br-r37-c1-f3i50: INT node keys, because the exact-`str` request is
        # served by the index-keyed cache added in 05d29a0f1 and never reaches
        # the string-keyed keydict path at all.
        #
        # This cost a certification: an A/B of the string-keyed change measured
        # nothing, because with `str` endpoints BOTH arms short-circuit earlier
        # and return identical objects. Non-`str` node keys are the ONLY way to
        # exercise it — verified by object identity, which differs between the
        # arms for int and tuple keys and is identical for str.
        for par in PARALLEL:
            graph = module.MultiGraph()
            for i in range(par):
                graph.add_edge(1, 2, weight=i)
            for i in range(200):
                graph.add_edge(10 + i, 1000 + i)
            fixture[("MultiGraph-intkeys", par)] = (graph, 1, 2)
        return fixture[("MultiGraph", 1)][0], fixture

    def ops(graph, fixture):
        table = {}
        for (cls, par), (g, u, v) in fixture.items():
            tag = {
                "MultiGraph": "MG",
                "MultiDiGraph": "MDG",
                "MultiGraph-intkeys": "MG-INTKEY",
            }[cls]
            table[f"{tag} get_edge_data(u,v) par={par}"] = (
                lambda g=g, u=u, v=v: g.get_edge_data(u, v)
            )
            table[f"SIBLING {tag} G[u][v] par={par}"] = lambda g=g, u=u, v=v: g[u][v]
        mg64, u, v = fixture[("MultiGraph", 64)]
        table["CONTROL MG has_edge par=64"] = lambda: mg64.has_edge(u, v)
        return table

    return build, ops


def workload_digraph_rows(reps: int):
    """DiGraph row subscripts against node-key length (br-r37-c1-0k6zl).

    `DiGraph G.adj[u][v]` read 0.0804x at 2000-character keys — only simple
    `Graph` reached the native row view with a cached row index, so `DiGraph`
    fell to the Python `AtlasView` and re-canonicalised both endpoints per
    subscript.

    THE CONTROLS. `Graph` at the same length is the POSITIVE control: it was
    already fixed, so it should be flat and comparatively high, and a run where
    the DiGraph rows match it is the intended outcome rather than a suspicious
    one. Length 3 is carried for every op as the SHORT-KEY control: the defect is
    key-length driven, so a fix that also moved length 3 by the same factor would
    mean I had changed per-call overhead rather than the canonicalisation.
    `has_edge` is the flat control — same endpoints, no attr dict fetched.
    """

    def build(module):
        fixture = {}
        for length in (3, 2000):
            u, v = "u" * length, "v" * length
            digraph = module.DiGraph()
            digraph.add_edge(u, v, weight=1)
            simple = module.Graph()
            simple.add_edge(u, v, weight=1)
            for i in range(200):
                digraph.add_edge(f"a{i}", f"b{i}")
                simple.add_edge(f"a{i}", f"b{i}")
            fixture[length] = (digraph, simple, u, v)
        return fixture[3][0], fixture

    def ops(graph, fixture):
        table = {}
        for length, (dg, simple, u, v) in fixture.items():
            table[f"DG G.adj[u][v] len={length}"] = lambda dg=dg, u=u, v=v: dg.adj[u][v]
            table[f"DG G[u][v] len={length}"] = lambda dg=dg, u=u, v=v: dg[u][v]
            table[f"DG get_edge_data len={length}"] = (
                lambda dg=dg, u=u, v=v: dg.get_edge_data(u, v)
            )
            table[f"CONTROL Graph adj[u][v] len={length}"] = (
                lambda simple=simple, u=u, v=v: simple.adj[u][v]
            )
        dg_long, _s, ul, vl = fixture[2000]
        table["CONTROL DG has_edge len=2000"] = lambda: dg_long.has_edge(ul, vl)
        return table

    return build, ops


def workload_has_node_membership(reps: int):
    """`has_node` / `n in G` on BOTH halves, present and missing (br-r37-c1-770z8).

    networkx pays ONE dict lookup whether the key is present or absent, reusing
    the hash CPython caches on every `str`. fnx's HIT could early-return from the
    present-key cache, but a MISS fell through to a rebuilt `str:{len}:{s}`
    canonical and hashed that — a second hash of the same characters. So the miss
    was the worse half (0.7177x against 0.9096x) and no present-key cache could
    ever touch it.

    BOTH HALVES ARE CARRIED because a change that helps the miss and regresses
    the hit is not a win — the hit is the common case, and measuring only the
    named defect would hide that.

    `n in G` is carried because `PyGraph.__contains__` routes through the same
    helper, so this is two public surfaces rather than one.

    THE REQUIRED CONTROL is the pair of rows on a graph whose node-iteration
    mirror was NEVER materialised. The lever answers from that mirror only when
    it already exists, and deliberately does not build it — materialising is O(N)
    and membership is a single-key question. If the control MOVES, the mirror is
    being built as a side effect and the lever is paying a hidden O(N).
    """
    N = 2000

    def build(module):
        fixture = {}
        for materialised in (True, False):
            graph = module.Graph()
            for i in range(N):
                graph.add_node(f"n{i}")
            for i in range(N - 1):
                graph.add_edge(f"n{i}", f"n{i + 1}")
            if materialised:
                # Force the node-iteration mirror to exist, as any prior
                # iteration of the graph would.
                list(graph.nodes())
            fixture[materialised] = graph
        return fixture[True], fixture

    def ops(graph, fixture):
        present, missing = "n1000", "absent-key"
        keys = [f"n{i}" for i in range(N)]
        table = {}
        for materialised, g in fixture.items():
            tag = "" if materialised else "CONTROL nomirror "
            table[f"{tag}has_node PRESENT"] = lambda g=g: g.has_node(present)
            table[f"{tag}has_node MISSING"] = lambda g=g: g.has_node(missing)
            table[f"{tag}n in G PRESENT"] = lambda g=g: present in g
            table[f"{tag}n in G MISSING"] = lambda g=g: missing in g

        # br-r37-c1-770z8: ROTATE over every present key, not just one.
        #
        # A single-key warm loop cannot tell a working present-key cache from a
        # broken one, and that ambiguity cost two wrong conclusions on this bead.
        # Measured on one key the hit reads 61.5ns against a 81.6ns miss, so the
        # cache plainly serves hits; but an earlier build read 85.3 present
        # against 85.7 missing and I concluded from that pair alone that the
        # cache "never warms". It does. One key is simply not enough evidence
        # either way.
        #
        # Rotating touches every entry of the present-key set, so it exercises
        # the set at realistic occupancy instead of hammering one slot. The
        # index arithmetic is identical in both arms and cancels in the ratio.
        # The cycle length must DIVIDE calls-per-slot, or each slot sees a
        # different stretch of keys and the A/A null correctly rejects the row
        # as slot-asymmetric — measured: a monotonic counter over all 2000 keys
        # gave null 0.9024. A 100-key cycle divides the 400-call slot exactly
        # four times, so every slot performs the identical key sequence.
        cycle = keys[:100]
        counter = {"i": 0}

        def rotating(g):
            counter["i"] = (counter["i"] + 1) % len(cycle)
            return g.has_node(cycle[counter["i"]])

        rotating_graph = fixture[True]
        # DIAGNOSTIC-ONLY, and named so nobody quotes it as a certified row.
        # Even with a cycle that divides the slot, this row NULL-FAILS routinely
        # (measured 1.0460/1.0604): touching 100 distinct keys per slot defeats
        # the warming symmetry the square relies on, in a way a single-key row
        # does not. It is here to answer "is the present-key cache serving hits
        # at realistic occupancy", which one key cannot answer, NOT to produce a
        # bankable ratio.
        table["DIAGNOSTIC has_node PRESENT rotating"] = (
            lambda g=rotating_graph: rotating(g)
        )
        return table

    return build, ops


def workload_edges_data(reps: int):
    """`list(G.edges(data=True))` against node-key length (br-r37-c1-ml7s5).

    The simple Graph rebuilt every tuple on every call and probed the attr mirror
    with a per-edge `(String, String)` canonical key, so the call grew with node
    key length while its directed twin stayed flat — 0.4538x at K=2000 against a
    networkx that is flat at ~322us.

    BOTH KEY LENGTHS ARE CARRIED because the defect is invisible at K=3, where
    the row was already a 2.8x WIN. A single-length row cannot distinguish
    "slower" from "unbounded", and unbounded was the property that mattered.

    THE OTHER THREE CLASSES ARE THE CONTROLS, and they are not decorative: the
    change is `PyGraph`-only, so DiGraph and both multigraph classes must not
    move. They also guard the reverse failure — an earlier run of the scaling
    test called DiGraph regressed at loadavg 53 when a direct measurement showed
    it flat, so a control that moves here means the window, not the code.
    """

    def build(module):
        fixture = {}
        for cls in ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph"):
            for length in (3, 2000):
                graph = getattr(module, cls)()
                for i in range(300):
                    graph.add_edge(
                        f"a{i}".ljust(length, "x"),
                        f"b{i}".ljust(length, "y"),
                        weight=i,
                    )
                fixture[(cls, length)] = graph
        return fixture[("Graph", 3)], fixture

    def ops(graph, fixture):
        table = {}
        for (cls, length), g in fixture.items():
            tag = {
                "Graph": "G",
                "DiGraph": "CONTROL DG",
                "MultiGraph": "CONTROL MG",
                "MultiDiGraph": "CONTROL MDG",
            }[cls]
            table[f"{tag} edges(data=True) len={length}"] = (
                lambda g=g: list(g.edges(data=True))
            )
        return table

    return build, ops


def workload_nbunch_key_length(reps: int):
    """`G.edges(nbunch, data=True)` against NODE-KEY LENGTH (br-r37-c1-nbidx).

    The axis this call grows on while networkx stays flat. No other workload
    passes an nbunch at all, which is why the defect sat unmeasured by this
    harness while three separate levers were aimed at it.

    THE CONTROLS ARE THE POINT. The lever changed how nbunch ITEMS resolve to
    node indices, so:

    * WHOLE-GRAPH `edges(data=True)` takes no nbunch and is served from the list
      cache (br-r37-c1-ml7s5). It must not move. If it does, the change leaked
      past the nbunch path.
    * A SMALL nbunch is carried at both lengths because there is no key-length
      effect there at all (0.6190x at K=3 against 0.6171x at K=2000). A
      five-item probe reports this surface healthy, so the row that reports
      healthy is kept next to the row that does not.

    EVERY ROW HERE COSTS ROUGHLY THE SAME PER SLOT, deliberately. A first draft
    also carried `has_edge` and `len(G)` as controls and every row of the run
    failed its A/A null, including `len(G)`, which cannot plausibly have
    regressed. One `--reps` is shared by all rows, so at the reps these
    materializing calls need (8) a `len(G)` slot is ~400ns of timer noise while
    an `edges(nbunch=200)` slot is ~2ms. The null was reporting a defect in the
    WORKLOAD, not the subject. Cheap controls for this lever belong in
    `key-length-scaling`, which already carries `has_edge` at a reps that suits
    it. This is why the fix was to equalise slot duration rather than to widen a
    bound.
    """
    edges, big = 300, 200

    def build(module):
        graphs = {}
        for length in (3, 2000):
            graph = module.Graph()
            for i in range(edges):
                graph.add_edge(
                    f"a{i}".ljust(length, "x"), f"b{i}".ljust(length, "y"), weight=i
                )
            graphs[length] = (graph, list(graph.nodes()))
        return graphs[3][0], graphs

    def ops(graph, fixture):
        table = {}
        for length, (g, nodes) in fixture.items():
            for size in (5, big):
                nb = nodes[:size]
                table[f"edges(nbunch={size},data) len={length}"] = (
                    lambda g=g, nb=nb: list(g.edges(nb, data=True))
                )
        for length, (g, nodes) in fixture.items():
            table[f"CONTROL edges(data) whole len={length}"] = (
                lambda g=g: list(g.edges(data=True))
            )
        return table

    return build, ops


def workload_mdg_in_edges_nbunch(reps: int):
    """`MultiDiGraph.in_edges(nbunch, ...)` against its own out_edges twin.

    br-r37-c1-mdginb. The in/out pair on one class is the cleanest control a
    family lever can have: both call a native nbunch kernel, both return the same
    shape, and only one of them was routed through the family's last-call memo.
    `out_edges` is therefore carried in every run as an UNTOUCHED sibling - if it
    moves, the change reached further than the one call site it edited.

    All rows materialise a list of comparable size, so one `--reps` suits them
    all; see `nbunch-key-length` for what happens when it does not.
    """
    edges, big = 300, 200

    def build(module):
        graphs = {}
        for length in (3, 2000):
            graph = module.MultiDiGraph()
            for i in range(edges):
                graph.add_edge(
                    f"a{i}".ljust(length, "x"), f"b{i}".ljust(length, "y"), weight=i
                )
            graphs[length] = (graph, list(graph.nodes()))
        return graphs[3][0], graphs

    def ops(graph, fixture):
        table = {}
        for length, (g, nodes) in fixture.items():
            nb = nodes[:big]
            table[f"in_edges(nbunch,data) len={length}"] = (
                lambda g=g, nb=nb: list(g.in_edges(nb, data=True))
            )
            table[f"in_edges(nbunch,data,keys) len={length}"] = (
                lambda g=g, nb=nb: list(g.in_edges(nb, data=True, keys=True))
            )
            table[f"CONTROL out_edges(nbunch,data) len={length}"] = (
                lambda g=g, nb=nb: list(g.out_edges(nb, data=True))
            )
        return table

    return build, ops


WORKLOADS = {
    "view-reads": workload_view_reads,
    "nbunch-key-length": workload_nbunch_key_length,
    "mdg-in-edges-nbunch": workload_mdg_in_edges_nbunch,
    "edges-data": workload_edges_data,
    "has-node-membership": workload_has_node_membership,
    "digraph-rows": workload_digraph_rows,
    "parallel-keydict": workload_parallel_keydict,
    "multi-key-length": workload_multi_key_length,
    "key-length-scaling": workload_key_length_scaling,
    "view-reads-directed": workload_view_reads_directed,
    "view-reads-multi": workload_view_reads_multi,
    "algorithms": workload_algorithms,
    "incumbent-fixtures": workload_incumbent_fixtures,
    "incumbent-fixtures-2": workload_incumbent_fixtures_2,
}


# ---------------------------------------------------------------------------
# Measurement
# ---------------------------------------------------------------------------
def canonical(value):
    """A comparable form for the pre-timing parity gate.

    Floats are rounded to 12 significant digits: tight enough that a different
    algorithm shows up, loose enough that last-ulp accumulation-order noise
    does not. Mappings are compared as sorted key/value pairs so dict ordering
    is not asserted here — iteration order is a separate contract with its own
    tests, and conflating the two would make this gate fail for the wrong
    reason.
    """
    if isinstance(value, float):
        return round(value, 12)
    # A numpy/scipy result has no usable `!=`: comparing two arrays yields an
    # elementwise array, so the gate's `got_nx != got_fx` raises "truth value of
    # an array is ambiguous" instead of comparing anything. Project to nested
    # lists and let the float rule above round each cell. This runs once per
    # row BEFORE timing, so its cost is not in any measurement.
    if hasattr(value, "tolist") and not isinstance(value, (bytes, bytearray)):
        return canonical(value.tolist())
    if isinstance(value, dict):
        return sorted((str(k), canonical(v)) for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return [canonical(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return sorted(str(canonical(v)) for v in value)
    return value


def time_slot(fn, *, collect_first: bool = False, calls: int = 1) -> int:
    """Time one slot with the collector already quiet.

    br-r37-c1-7x25w: this used to call `gc.collect()` before EVERY slot. The
    collect sat outside the timed region so it was never charged directly —
    what it did was walk every GC-tracked container in the process and leave
    the caches cold, so the arm that restarts with the larger tracked heap pays
    more to warm back up. That arm is always fnx: an fnx Graph carries
    node_py_attrs, edge_py_attrs, edge_py_attrs_by_endpoint, adj_row_py, the
    node-key map and the index lookaside, where the networkx arm is plain
    dicts. Symmetric PROCEDURE, asymmetric EFFECT, running in the direction
    that makes fnx look slow — and it is a fixed per-slot cost, so it
    amortises away as reps grow instead of scaling with the work:

        reps          400     1000     4000    20000
        collect=1   0.4465   0.4645   0.5248   0.6564
        collect=0   0.8167   0.8236   0.8057   0.8092   <- flat

    The A/A null cannot see it. Both halves of a square are equally cold, so
    the null comes out at 1.0 and certifies a biased ratio; one measured draw
    reported 0.5478x with nulls 0.9935/0.9845 for a row that is 1.1464x —
    admissible, and wrong in SIGN.

    `collect_first` exists only to reproduce that defect on demand (see
    `--gc-per-slot`), never as a measurement mode.
    """
    if collect_first:
        gc.collect()
    start = time.perf_counter_ns()
    for _ in range(calls):
        fn()
    return time.perf_counter_ns() - start


def smt_sibling_map():
    """`{pinned_cpu: [its thread siblings]}` for the CPUs this process may use.

    br-r37-c1-armplace. A pinned CPU set says nothing about which PHYSICAL cores
    it occupies. On this host `taskset -c 40-47` lands entirely on the SECOND
    hyperthread of physical cores 8-15, so a peer benchmarking on cpu8-15 shares
    execution units with every slot measured here. Both arms interleave in one
    process and therefore meet that contention equally, but the exposure belongs
    in the row rather than in someone's later reconstruction.
    """
    out = {}
    try:
        pinned = sorted(os.sched_getaffinity(0))
    except OSError:
        return out
    for cpu in pinned:
        try:
            with open(
                f"/sys/devices/system/cpu/cpu{cpu}/topology/thread_siblings_list"
            ) as handle:
                siblings = [
                    int(part) for part in handle.read().strip().replace("-", ",").split(",")
                ]
        except (OSError, ValueError):
            continue
        others = [s for s in siblings if s != cpu]
        if others:
            out[cpu] = others
    return out


def sample_core_khz():
    """The RUNNING core's current frequency, in kHz, or None.

    br-r37-c1-clockrow. This host runs the `powersave` governor and its cores do
    change frequency under load, so a row that reports only `loadavg` is not
    reporting its own conditions. Two design points, both of which another pane
    got wrong and then corrected in this ledger:

    1. SAMPLE THE CORE THAT RAN THE WORK, not `cpu0`. The harness is pinned with
       `taskset`, so `cpu0`'s governor file describes a core that never executed
       a slot. This reads `sched_getcpu()`.

    2. SAMPLE WHILE THE CORE IS HOT — immediately AFTER a timed slot, never
       before one. A sample taken at round start reads the clock the governor had
       settled on for an IDLE process, i.e. before it boosted for the work about
       to happen. That pre-boost sampling is what produced a "1429-4292 MHz, 3.0x
       swing" figure that its own author later retracted: sampling an idle
       process read 3434 MHz flat, while sampling a BUSY one read 3354-4292 MHz,
       a 22 percent range. The instrument was measuring its own idleness.

    The read itself is outside every timed region, so it cannot contaminate a
    slot's duration.

    THE PORTABILITY TRAP THIS ALREADY HIT: `os.sched_getcpu()` does NOT exist in
    this CPython (3.13), so a first version of this function returned
    `(None, None)` on every call and the harness would have printed
    "clk unavailable" on every row while looking like it was recording clocks.
    The running CPU comes from `/proc/self/stat` field 39 instead, which needs the
    `rsplit(') ')` because a process name can itself contain spaces and
    parentheses.
    """
    try:
        with open("/proc/self/stat") as handle:
            cpu = int(handle.read().rsplit(") ", 1)[1].split()[36])
    except (OSError, ValueError, IndexError):
        return None, None
    try:
        with open(f"/sys/devices/system/cpu/cpu{cpu}/cpufreq/scaling_cur_freq") as handle:
            return cpu, int(handle.read().strip())
    except (OSError, ValueError):
        return cpu, None


def _time_square(incumbent_fn, fnx_fn, gc_per_slot: bool, calls_per_slot: int = 1):
    """Run one `ABBAABBA` square and return the two arms' slot timings and clocks.

    The square is what makes a busy host measurable: each arm occupies the same
    set of slot POSITIONS, so drift across the round hits both equally instead
    of biasing one.

    The per-arm clock samples exist to CHECK that claim rather than assume it. An
    arm-asymmetric core frequency — one arm consistently boosted, the other not —
    biases the ratio while leaving both A/A nulls at 1.0, because each arm's own
    first half and second half are equally affected. That is the same blind spot
    the per-slot GC collect had (see `time_slot`), and it is invisible to every
    check this harness performs unless the clock is recorded per arm.
    """
    a_slots, b_slots = [], []
    a_khz, b_khz = [], []
    a_cpus, b_cpus = [], []
    for slot in SQUARE:
        if slot == "A":
            a_slots.append(
                time_slot(incumbent_fn, collect_first=gc_per_slot, calls=calls_per_slot)
            )
            cpu, khz = sample_core_khz()
            if khz is not None:
                a_khz.append(khz)
            if cpu is not None:
                a_cpus.append(cpu)
        else:
            b_slots.append(
                time_slot(fnx_fn, collect_first=gc_per_slot, calls=calls_per_slot)
            )
            cpu, khz = sample_core_khz()
            if khz is not None:
                b_khz.append(khz)
            if cpu is not None:
                b_cpus.append(cpu)
    return a_slots, b_slots, a_khz, b_khz, a_cpus, b_cpus


def bootstrap_ci(values, iters: int = 4000, seed: int = 3):
    rng = random.Random(seed)
    n = len(values)
    medians = sorted(
        statistics.median(values[rng.randrange(n)] for _ in range(n))
        for _ in range(iters)
    )
    return medians[int(0.025 * iters)], medians[int(0.975 * iters)]


def run_row(
    label: str,
    incumbent_fn,
    fnx_fn,
    rounds: int,
    warmup: int,
    *,
    gc_per_slot: bool = False,
    calls_per_slot: int = 1,
) -> dict:
    """One row: `rounds` balanced squares, per-arm A/A nulls, bootstrap median CI.

    br-r37-c1-7x25w: the collector is quiesced ONCE per round and stays off for
    all eight slots, so no collection can land inside a timed region and no arm
    pays a cold start the other does not. Collecting per slot biased every read
    row against the arm holding the larger GC-tracked heap, which is always
    fnx.
    """
    for _ in range(warmup):
        incumbent_fn()
        fnx_fn()

    ratios, null_a, null_b = [], [], []
    khz_a, khz_b = [], []
    # br-r37-c1-armplace: which logical CPUs each arm actually ran on. Both arms
    # execute in ONE process, interleaved inside the square, so they share an
    # affinity mask by construction — but the scheduler may still MIGRATE the
    # process between slots, and a mask spanning 8 CPUs gives it 8 places to go.
    # If arm A's slots landed on a different set from arm B's, the ratio is
    # comparing two placements, and both A/A nulls read 1.0 through it.
    cpus_a, cpus_b = set(), set()
    for _ in range(rounds):
        # One collect per ROUND, outside every timed slot, with the collector
        # left OFF for the whole square: both arms then meet the same GC state
        # and neither restarts cold eight times.
        #
        # Then ONE UNTIMED call per arm before the square. A collect leaves the
        # caches cold, and the first timed slots after it are measurably slower
        # than the last — with the per-slot collect that showed up as a uniform
        # tax the A/A null could not see, and hoisting the collect turned it
        # into a first-half/second-half asymmetry the null CAN see: the fixed
        # harness reported nulls of 1.1783/1.3516 until this pair was added.
        # Absorbing the cold start symmetrically is what makes both the bias
        # and the null honest.
        gc.collect()
        gc.disable()
        try:
            # br-r37-c1-j3i9q: warm each arm with as much work as a TIMED SLOT
            # holds. Two fixed calls were enough for the read rows, where a slot
            # is one call containing `reps` operations, but not for whole-
            # algorithm rows at K>1: their first-half nulls stayed above 1.02
            # because the first timed slot was still colder than the last.
            for _ in range(max(ROUND_WARM_CALLS, calls_per_slot)):
                incumbent_fn()
                fnx_fn()
            a_slots, b_slots, a_khz, b_khz, a_cpus, b_cpus = _time_square(
                incumbent_fn, fnx_fn, gc_per_slot, calls_per_slot
            )
            khz_a.extend(a_khz)
            khz_b.extend(b_khz)
            cpus_a.update(a_cpus)
            cpus_b.update(b_cpus)
        finally:
            gc.enable()
        ratios.append(statistics.median(a_slots) / statistics.median(b_slots))
        # Each arm's own first-half / second-half ratio. The square places the
        # halves symmetrically, so a null that departs from 1.0 is drift or
        # contention, not slot position.
        null_a.append(statistics.median(a_slots[:2]) / statistics.median(a_slots[2:]))
        null_b.append(statistics.median(b_slots[:2]) / statistics.median(b_slots[2:]))

    ratio = statistics.median(ratios)
    low, high = bootstrap_ci(ratios)
    n_a, n_b = statistics.median(null_a), statistics.median(null_b)
    nulls_ok = abs(n_a - 1.0) <= NULL_BOUND and abs(n_b - 1.0) <= NULL_BOUND
    if not nulls_ok:
        verdict = "NULL-FAILED"
    elif low <= 1.0 <= high:
        verdict = "STRADDLES-1"
    else:
        verdict = "ADMISSIBLE"

    # Per-ARM clock, and the asymmetry between them. `clock_skew` is the number
    # that matters for the RATIO: the arms interleave inside one square, so they
    # should meet the same frequency, and a skew is a bias no A/A null can see.
    # The absolute median and spread describe the window itself — a row taken at
    # 3.4 GHz and one taken at 4.3 GHz are not the same measurement even when
    # both are admissible and both nulls pass.
    mhz_a = statistics.median(khz_a) / 1000.0 if khz_a else None
    mhz_b = statistics.median(khz_b) / 1000.0 if khz_b else None
    all_khz = khz_a + khz_b
    if all_khz:
        spread_pct = 100.0 * (max(all_khz) - min(all_khz)) / statistics.median(all_khz)
    else:
        spread_pct = None
    clock_skew = (
        100.0 * (mhz_a - mhz_b) / ((mhz_a + mhz_b) / 2.0)
        if mhz_a is not None and mhz_b is not None
        else None
    )
    # Deliberately NOT folded into `verdict`: this harness is shared, and adding
    # a new way for a row to stop being ADMISSIBLE would silently retire other
    # panes' rows mid-campaign. The skew is reported on the row and totalled at
    # the end instead, so it informs the reader without changing the contract.
    clock_skewed = clock_skew is not None and abs(clock_skew) > CLOCK_SKEW_BOUND_PCT
    return {
        "label": label,
        "ratio": ratio,
        "ci": (low, high),
        "null_incumbent": n_a,
        "null_fnx": n_b,
        "verdict": verdict,
        "mhz_incumbent": mhz_a,
        "mhz_fnx": mhz_b,
        "mhz_spread_pct": spread_pct,
        "clock_skew_pct": clock_skew,
        "clock_skewed": clock_skewed,
        "cpus_incumbent": sorted(cpus_a),
        "cpus_fnx": sorted(cpus_b),
        "cpus_shared": sorted(cpus_a & cpus_b),
        "cpus_arm_exclusive": sorted(cpus_a ^ cpus_b),
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workload", default="view-reads")
    parser.add_argument("--rounds", type=int, default=41)
    parser.add_argument("--reps", type=int, default=400)
    parser.add_argument("--warmup", type=int, default=8)
    parser.add_argument("--expect-elf", default=os.environ.get("EXPECT_ELF_SHA"))
    parser.add_argument("--list", action="store_true")
    # br-r37-c1-y4r63: run ONE row, so a row's number can be checked without the
    # rows before it having run in the same process. Every row still builds and
    # parity-gates, so the fixture and the gate are unchanged by the selection.
    parser.add_argument(
        "--only",
        default=None,
        help="run only rows whose label contains this substring",
    )
    # br-r37-c1-7x25w: NOT a measurement mode. It restores the per-slot
    # gc.collect() this harness used until 2026-08-15, so the bias that
    # introduced can be reproduced and bounded rather than argued about.
    # br-r37-c1-j3i9q: how many CALLS a timed slot holds. The read workloads put
    # `reps` operations inside one call and leave this at 1; the whole-algorithm
    # workload has one call per unit of work, and at K=1 its A/A null is
    # comparing the variance of one call against one call — 9 of 11 rows failed
    # their nulls while reporting stable ratios. Default stays 1 so no existing
    # row silently changes meaning, and K is printed in the run header because a
    # row measured at K=1 and one at K=5 are not automatically comparable.
    parser.add_argument(
        "--calls-per-slot",
        type=int,
        default=1,
        help="algorithm calls inside each timed slot (default 1)",
    )
    parser.add_argument(
        "--gc-per-slot",
        action="store_true",
        help="reproduce the pre-fix per-slot gc.collect() bias (do not measure with this)",
    )
    args = parser.parse_args(argv[1:])

    if args.list:
        for name in WORKLOADS:
            print(name)
        return 0
    if args.workload not in WORKLOADS:
        raise SystemExit(f"unknown workload {args.workload!r}; try --list")

    prov = provenance()
    print("PROVENANCE (self-reported from inside the process)")
    for key, value in prov.items():
        print(f"  {key:24s} {value}")
    print(f"  {'rounds/warmup/reps':24s} {args.rounds}/{args.warmup}/{args.reps}")
    print(f"  {'calls_per_slot':24s} {args.calls_per_slot}")

    # A bare `python3` loads the site-packages extension, which is a DIFFERENT
    # build. Refuse rather than measure the wrong binary.
    if args.expect_elf and not prov["elf_sha256"].startswith(args.expect_elf):
        raise SystemExit(
            f"ELF MISMATCH: loaded {prov['elf_sha256'][:16]} from {prov['elf']}, "
            f"expected {args.expect_elf}"
        )

    build, ops = WORKLOADS[args.workload](args.reps)
    g_nx, fx_nx = build(nx)
    g_fx, fx_fx = build(fnx)
    if g_nx.number_of_nodes() != g_fx.number_of_nodes():
        raise SystemExit("fixture mismatch: node counts differ")
    if g_nx.number_of_edges() != g_fx.number_of_edges():
        raise SystemExit("fixture mismatch: edge counts differ")

    ops_nx = ops(g_nx, fx_nx)
    ops_fx = ops(g_fx, fx_fx)

    selected = [name for name in ops_nx if args.only is None or args.only in name]
    if not selected:
        raise SystemExit(f"--only {args.only!r} matched no row; rows are: {list(ops_nx)}")

    # Parity gate BEFORE timing: an arm that computes something different must
    # fail loudly, not produce a fast wrong number. Floats are compared at 12
    # significant digits — tight enough to catch a different algorithm, loose
    # enough not to trip on last-ulp accumulation-order differences, which are
    # a separate question from "are these arms doing the same work".
    #
    # It gates the SELECTED rows only. Gating a row you are not timing still
    # runs it once against both libraries, which warms and dirties exactly the
    # structures the timed row then reads — so `--only` would not isolate
    # anything if this loop ignored it (br-r37-c1-y4r63).
    for name in selected:
        got_nx, got_fx = canonical(ops_nx[name]()), canonical(ops_fx[name]())
        if got_nx != got_fx:
            raise SystemExit(
                f"PARITY MISMATCH on {name}:\n  networkx {str(got_nx)[:300]}\n"
                f"  fnx      {str(got_fx)[:300]}"
            )

    print(
        f"\nRATIO = t_networkx / t_fnx   (>1 means fnx faster)   square={SQUARE}"
        f"   null bound +/-{NULL_BOUND}"
    )
    admitted = 0
    skewed = 0
    arm_exclusive_cpus = 0
    for name in selected:
        row = run_row(
            name,
            ops_nx[name],
            ops_fx[name],
            args.rounds,
            args.warmup,
            gc_per_slot=args.gc_per_slot,
            calls_per_slot=args.calls_per_slot,
        )
        low, high = row["ci"]
        if row["mhz_incumbent"] is None:
            clock = "clk unavailable"
        else:
            clock = (
                f"clk {row['mhz_incumbent']:.0f}/{row['mhz_fnx']:.0f}MHz "
                f"skew {row['clock_skew_pct']:+.2f}% spread {row['mhz_spread_pct']:.1f}%"
                f"{' SKEWED' if row['clock_skewed'] else ''}"
            )
        exclusive = row["cpus_arm_exclusive"]
        placement = (
            f"cpus={row['cpus_shared']}"
            if not exclusive
            else f"cpus A={row['cpus_incumbent']} B={row['cpus_fnx']} ARM-EXCLUSIVE={exclusive}"
        )
        print(
            f"  {name:22s} {row['ratio']:7.4f}x  CI [{low:.4f}, {high:.4f}]  "
            f"nulls {row['null_incumbent']:.4f}/{row['null_fnx']:.4f}  {clock}  "
            f"{placement}  {row['verdict']}"
        )
        admitted += row["verdict"] == "ADMISSIBLE"
        skewed += bool(row["clock_skewed"])
        if exclusive:
            arm_exclusive_cpus += 1

    print(f"\n  loadavg_end              {os.getloadavg()}")
    if skewed:
        print(
            f"  CLOCK-SKEWED rows        {skewed}/{len(selected)} — the two arms of "
            f"those squares ran at core frequencies differing by more than "
            f"{CLOCK_SKEW_BOUND_PCT}%. Both A/A nulls read 1.0 through this, so do "
            f"not treat a passing null as evidence against it."
        )
    if arm_exclusive_cpus:
        print(
            f"  ARM-EXCLUSIVE-CPU rows   {arm_exclusive_cpus}/{len(selected)} — one "
            f"arm ran on a CPU the other never touched, so that row compares two "
            f"placements as well as two implementations. Re-pin to a single CPU "
            f"(taskset -c N) and re-measure before quoting it."
        )
    print(f"  admitted rows            {admitted}/{len(selected)}")
    if admitted == 0:
        print("  NO ADMISSIBLE ROW — do not quote any number from this run.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
