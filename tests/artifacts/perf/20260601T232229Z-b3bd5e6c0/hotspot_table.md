# FrankenNetworkX — Profiling Pass: Ranked Hotspot Table

- **Run ID:** `20260601T232229Z-b3bd5e6c0`
- **Owner:** TealSpring (claude-code) — measurement only, no optimization
- **Scenario:** `fnx_algorithms::betweenness_centrality` (Brandes) on a connected sparse random graph, **N=1500 nodes, M=6000 edges (avg degree 8), fixed SplitMix64 seed**.
- **Success metric:** p95 wall-clock per call (single-threaded) + peak RSS.
- **Baseline:** p50 **1024 ms**, p95 **1097 ms**, p99 1187 ms (30 samples, CV 4.7%); peak RSS **11.4 MB**. See `baseline_summary.json` / `fingerprint.json`.

## Profiler note (three independent methods, triangulated)

`perf record` and `samply` both **failed on this host**: the swarm host is saturated
(load_avg ~51 on 64 cores; multiple agents profiling concurrently), which (a) exhausts
the host-wide `perf_event` mmap/mlock budget → `mmap failed`, and (b) wedges `perf record`
finalization (process parks in `sigsuspend`, survives SIGINT; corrupt 0-size data header).
Partial/corrupt `perf_*.data` files are retained for provenance but are NOT readable.

Attribution was instead triangulated across **three independent, perf_event-free methods**
that all agree:
1. **`PERF_SPANS=1` phase timers** (env-gated source instrumentation) → BFS phase 93%.
2. **`ALGO=lookup_sweep` microbench** (isolates inner-loop `neighbors_iter`+`get_node_index`
   over the full edge set, non-distorting) → ~76% of total.
3. **`pprof` in-process sampling** (`PPROF=1`, SIGPROF-based — immune to the `perf_event`
   mmap failure; harness support added by a peer agent) → **`get_node_index` = 68.4%** of
   samples; `get_index_of`(IndexMap) 66%, `find_inner`(hashbrown) 48%, `hash_one<&str>`
   (node-name string hashing) **32%**. See `pprof_top.txt`.

Convergence of all three (93% BFS ⊃ 76% lookups ⊃ 68% `get_node_index`) makes the hotspot
attribution conclusive.

## Ranked hotspots

| Rank | Location | Metric | Value | Category | Evidence |
|------|----------|--------|-------|----------|----------|
| 1 | `fnx-algorithms` `betweenness_centrality_generic` inner loop — **String→index adjacency resolution**: `graph.neighbors_iter(nodes[v])` + `graph.get_node_index(w_name).unwrap()` (lib.rs:3158-3161) | cumulative self-time | **≈778 ms / 1025 ms (≈76%)** | CPU | `lookup_sweep` microbench = 0.519 ms/full-edge-sweep × 1500 sources = 778 ms; `phase_split.txt` BFS phase = 946 ms (93%) |
| 2 | `fnx-algorithms` `closeness_centrality_generic` — **same** string-keyed BFS-per-source pattern (`in_neighbors_iter(nodes[v])` + index resolve, lib.rs:~2238-2245) | per-call latency | **826 ms** | CPU | cross-algo harness; shares root cause with #1 |
| 3 | `betweenness_centrality_generic` per-source state alloc `vec![Vec::<usize>::new(); n]` ×n sources + predecessor `push` (lib.rs:3144, 3170) | alloc phase | ≈19-22 ms (2%) | alloc | `phase_split.txt` alloc_phase_ms=19.4-21.8 |
| 4 | `betweenness_centrality_generic` dependency-accumulation phase (lib.rs:3181-3192) | cumulative | ≈29 ms (3%) | CPU | `phase_split.txt` accum_phase_ms=29.0-29.3 |

### Root cause (shared by #1 and #2 — systemic)

Every BFS-per-source centrality (`betweenness`, `closeness`, `harmonic`) stores adjacency
keyed by node **name strings** and, in the innermost loop, (a) looks up a node's neighbor
iterator by string and (b) resolves each neighbor **name → integer index** via a HashMap
(`get_node_index`). At N=1500/M=6000 the inner loop runs **18,000,000** times per
betweenness call; ~76% of wall-clock is spent hashing node-name strings and probing the
index HashMap — not in the actual graph-theoretic work.

### Hypothesized fix (for the optimizer agents — NOT applied in this pass)

**The substrate already exists.** Commit `2c8013ac6` ("perf(fnx-classes): add integer-indexed
adjacency for O(1) BFS traversal") added `Graph::adj_indices: Vec<Vec<usize>>` and the accessor
`Graph::neighbors_indices(node_idx: usize) -> Option<&[usize]>` (fnx-classes/src/lib.rs:293).
Several algorithms already use it (e.g. lib.rs:1870, 1999, 13795), but **betweenness, closeness,
and harmonic centrality were missed** and still walk the string path.

Fix = migrate the inner loops from
`graph.neighbors_iter(nodes[v])` → `for w_name in ...` → `graph.get_node_index(w_name)`
to the index-native `graph.neighbors_indices(v)` → `for &w in ...` (no string hash, no HashMap
probe). Expected ~3× on betweenness (lookup share ~68-76%) and similar on closeness/harmonic.
Note `neighbors_indices` is currently on the concrete `Graph`/`DiGraph`, not the `GraphView`
trait the `*_generic` fns use — the optimizer may need to add it to `GraphView` (with a
`neighbors_indices`/`in_neighbors_indices` pair for directed). Verify parity via the existing
conformance suite (scores/order unchanged) and re-baseline with this harness
(`ALGO=betweenness|closeness N=1500 DEG=8`).

## Scaling law

Brandes is O(V·E); the string-lookup share is structural (one resolve per edge traversal,
repeated per source), so it scales with the algorithm — at N=1500/M=6000 it is ~1.0 s/call
and ~76% lookup-bound.

## Artifacts in this directory

- `fingerprint.json` — env/host/toolchain/build fingerprint
- `baseline_summary.json` + `baseline_betweenness_raw.jsonl` — 30-run baseline
- `phase_split.txt` — `PERF_SPANS=1` BFS vs accum vs alloc phase timings
- `cross_algo.txt` — per-call latency for betweenness/pagerank/closeness/components/dijkstra
- `hypothesis_ledger.md` — supports/rejects with evidence
- `perf_*.data`, `samply.log` — failed sampler attempts (provenance only; unreadable)
