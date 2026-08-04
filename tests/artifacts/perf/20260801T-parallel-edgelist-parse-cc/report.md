# Parallel edge-list parse — the last serial stage of the analytics pass (cc, 2026-08-01)

Status: **kernel change + measurement artifact.** `read_edgelist` went from **3.0–3.3x to 9.77x**
against live NetworkX 3.6.1, and the whole-job analytics pass on a real graph measured
**1228.9x** (CI [1194.3, 1350.4]). Correctness is held by a 72-check differential oracle against
live nx plus the repo's own suites (49 941 Python tests, 84 fnx-classes Rust tests).

All numbers below are from one binary: fnx ELF SHA-256
`9f8de221eecd51e8d8b0bcfbc7d1f776ff6866525b3621c20451cf76be62e86f`, cargo profile `release`.

## Why this target

The 2026-07-30 parallel-analytics artifact left the whole job dominated by two stages that were
already parallel (`betweenness_exact` at cpu/wall 42.6, `closeness` at 46.7). Profiling the job
again on HEAD ranked fnx's own self-time on `ca-AstroPh`:

| stage | fnx wall | share | cpu/wall |
|---|--:|--:|--:|
| `betweenness_exact` | 1424.9 ms | 60.3% | 42.60 |
| `closeness` | 559.3 ms | 23.7% | 46.66 |
| **`read_edgelist`** | **294.2 ms** | **12.5%** | **1.01** |
| `average_clustering` | 39.6 ms | 1.7% | 1.06 |
| everything else | < 20 ms each | | |

`read_edgelist` was the **largest fully-serial stage in the job** — 63 cores idle while it ran —
and the worst ratio on the board. Once the centrality stages run at 42–46x, Amdahl points straight
at the parser.

Two claims from the prior artifact were **re-measured and found stale, in both directions**:

* it reported `read_edgelist` at **0.91x (a loss)**; on HEAD it was already **3.0–3.3x (a win)**.
  The old number was measured against a site-packages install whose `__init__.py` was 1444 lines
  behind the repo, so it timed an older code path, not the shipped one.
* the same profile appeared to show `pagerank` at 76 ms and cpu/wall 1.01, which looked like a
  serial-PageRank lever. Re-measured with replicates, PageRank is **2.0 ms / 4.3 ms and already
  35–48x**; the 76 ms was first-call cost. That lever was dropped before any code was written.

## What changed

`parse_edgelist_simple_content` (`crates/fnx-python/src/readwrite.rs`) was rewritten from a
serial, string-keyed scan into a chunked, dictionary-encoding one:

1. **Parallel scan.** The payload is cut into slices on line boundaries and scanned over the rayon
   pool. The scan touches no Python object, so it needs no GIL. Node tokens are `&str` slices
   borrowed from the payload — no text is copied.
2. **Dictionary encoding.** Each chunk interns its own tokens to dense local ids; an ordered merge
   folds the per-chunk dictionaries in chunk order, which is line order, reproducing global
   first-appearance node order exactly.
3. **One Python object per distinct node.** The old scan called `canon_token` per edge *endpoint*,
   and it returned `c.clone()` — a fresh `String` every time. On `ca-AstroPh` that was **792 320
   heap allocations where 18 772 were needed**. NetworkX never pays this: it uses the Python `str`
   object itself as the dict key, with a cached hash.
4. **Index-keyed bulk build.** Node indices are already in first-seen order, so the existing
   `extend_fresh_index_edges_with_attrs_unrecorded` applies them directly instead of re-hashing
   every endpoint's canonical key through the string-keyed node map.

A second change came out of profiling the result (`crates/fnx-classes`, 6 bulk-edge builders):
`existing.extend(attrs)` on a duplicate edge built and dropped a `BTreeMap` iterator even when
`attrs` was empty. An edge list that names each edge in both directions is 50% duplicates, so this
no-op was **11.3% of parse self-time** (`dying_next` 7.20% + `Extend::fold` 4.11%). Skipping the
merge when there is nothing to merge is observationally identical.

Chunk count is sized by **work, not core count** (`CHUNK_TARGET_BYTES = 512 KiB`). The ordered
merge is serial and its cost grows with the chunk count, so splitting finer than the payload
deserves loses more in the merge than it gains in the scan — measured, 8 chunks beat 64.

## Measured — nx 3.6.1 live in the same invocation, arms interleaved

Host `thinkstation1`, AMD Ryzen Threadripper PRO 5975WX, 32 physical / 64 SMT, Python 3.13.7,
NetworkX **3.6.1** live in-process, `NETWORKX_AUTOMATIC_BACKENDS` unset.

### `read_edgelist` on `ca-AstroPh` (18 772 n, 198 110 e, gzipped, 5.3 MB decompressed)

| | wall | cpu/wall |
|---|--:|--:|
| nx 3.6.1 | 691.5 ms | 1.00 |
| fnx | **73.7 ms** | 1.48 |
| **ratio** | **9.77x** — CI [8.99, 10.01] | |

11 interleaved replicates. A/A null: fnx median 0.9630 (half-width 0.1236), nx median 1.0187
(half-width 0.0394). Baseline before the change, same measurement path: **3.0–3.3x**.
The Rust parse alone went **287.2 ms → 85.5 ms**.

### Thread sweep — separating "left Python" from "used the cores"

| threads | fnx wall | cpu/wall | vs nx |
|--:|--:|--:|--:|
| 1 | 101.18 ms | 1.00 | 6.66x |
| 2 | 87.82 ms | 1.15 | 8.07x |
| 4 | 83.21 ms | 1.26 | 8.88x |
| 8 | **72.88 ms** | 1.37 | **9.08x** |
| 16 | 84.08 ms | 1.36 | 8.42x |
| 32 | 94.40 ms | 1.35 | 7.76x |
| 64 | 96.18 ms | 1.36 | 7.95x |

The `--threads 1` row is load-bearing. **6.66x is what leaving interpreted Python buys** — the
dictionary encoding and the removed allocations, available on one core. The **1 → 8 step is the
capability NetworkX lacks**, and it is worth a further 1.39x. cpu/wall plateaus at ~1.36 past 8
threads because the chunk count is capped by payload size (5.3 MB → 10 chunks), which is the
intended behaviour; the extra rayon workers only add scheduling overhead.

Honest attribution: **roughly two-thirds of this win is the allocation/structure fix and one-third
is the parallelism.** After the change, profiling shows the scan at ~6% of self-time, with graph
construction (IndexMap edge dedup, adjacency pushes) as the remainder — the parse is no longer
scan-bound.

### Whole job — `facebook_combined` (4039 n, 88 234 e), 8 interleaved replicates

`read_edgelist → remove_self_loops → connected_components → degree_assortativity →
average_clustering → core_number → pagerank → betweenness_centrality (EXACT) → closeness`

| stage | nx wall | nx cpu/wall | fnx wall | fnx cpu/wall | fnx threads | speedup |
|---|--:|--:|--:|--:|--:|--:|
| read_edgelist | 0.128 s | 1.02 | 0.016 s | 1.19 | 1 | 8.0x |
| remove_self_loops | 0.000 s | 6.32 | 0.000 s | 26.37 | 1 | 4.5x |
| connected_components | 0.009 s | 1.23 | 0.001 s | 3.43 | 1 | 9.6x |
| degree_assortativity | 0.136 s | 1.02 | 0.001 s | 4.31 | 1 | 188.0x |
| average_clustering | 1.291 s | 1.00 | 0.014 s | 1.17 | 1 | 94.3x |
| core_number | 0.085 s | 1.03 | 0.002 s | 2.42 | 1 | 50.6x |
| pagerank | 0.076 s | 1.03 | 0.004 s | 1.67 | 1 | 19.0x |
| betweenness_exact | 93.306 s | 1.00 | 0.062 s | 40.38 | 65 | 1503.3x |
| closeness | 35.480 s | 1.00 | 0.005 s | 23.15 | 65 | 6977.2x |
| **TOTAL** | **131.011 s** | **1.00** | **0.105 s** | **25.34** | **65** | **1253.3x** |

Median of the eight per-replicate whole-job ratios: **1228.9x**, CI **[1194.3, 1350.4]**.
(The table's 1253.3x is the median of the per-stage TOTAL walls; both statistics are reported
rather than the more flattering one alone.)

**NetworkX sits at cpu/wall 1.00–1.03 on every substantial stage of every replicate.** That flat
1.00 is the missing capability, observed rather than asserted.

Note `read_edgelist` shows 1 thread here: `facebook_combined` decompresses to ~1.1 MB, which at a
512 KiB chunk target is 2 chunks, so the parallel scan barely engages. Its 8.0x on this graph is
almost entirely the serial structural win. The parallel path is what the `ca-AstroPh` numbers
above exercise.

### Honest caveats

* **The substrate is a shared 64-thread box** with peer agents on it; load ranged 13–50 across the
  session. The whole-job A/B above ran at load 13–17 and is well conditioned (CI ±6%). An earlier
  run of the same job at load 22–50 gave 1045.7x with CI [332.2, 1312.0] — same direction, far
  wider. Contention starves fnx's parallel stages while barely touching single-threaded nx, so
  **the bias runs against fnx**.
* **The whole-job A/A null half-width is 0.3655**, large in absolute terms because the fnx arm is
  ~0.1 s. The effect is ~3000x that spread so the verdict is not in doubt, but this is not a
  quiet-host measurement and is not presented as one.
* **One digest key differs between engines: `degree_assortativity`**, at
  `0.06357722918564918` vs `0.06357722918564943` — a 2-ULP float-summation-order difference.
  It is **pre-existing and not from this change**: the 2026-07-30 study JSON already contains both
  values, and rebuilding fnx's graph as a native `nx.Graph` and running nx's own kernel returns
  nx's value exactly, so the reader's output is content-identical. Every other digest key — node
  count, edge count, component sizes, max core, and the top-10 lists for pagerank, betweenness and
  closeness — matches exactly.

## Correctness

* **72-check differential oracle vs live nx** (`diff_edgelist.py`), comparing node insertion
  order, edge insertion order, adjacency row order, edge data, and exact exception type/message.
  Covers empty files, comment-only files, blank/whitespace/single-token lines, CRLF, self-loops,
  duplicate edges, inline `#`, UTF-8 node names, the weighted reader (including `inf`/exponent
  spellings), every bail path, and the real staged SNAP graphs. **0 mismatches.**
  Because the parallel path only engages above the chunk threshold, every large case is run at
  five node-token widths so chunk cuts land at different offsets within a line, and a mid-file
  bail is injected at 0%, 50% and 99% to confirm one chunk bails the whole parse.
* `pytest tests/python` — **49 941 passed**, 1065 skipped. The 7 failures in
  `test_coverage_gaps.py` are environmental (the coverage generator spawns a subprocess whose
  interpreter has no `networkx` at all) and are unrelated to this change.
* `cargo test -p fnx-classes` — **84 passed, 0 failed**, including
  `extend_edges_with_attrs_unrecorded_matches_add_edge_with_attrs`, the observational-parity test
  for the bulk builder this change touches.

## Reproduce

```bash
python3 tests/artifacts/perf/20260801T-parallel-edgelist-parse-cc/diff_edgelist.py
python3 tests/artifacts/perf/20260801T-parallel-edgelist-parse-cc/bench_edgelist.py \
    --role worker --graph ca-AstroPh --reps 11 --aa
python3 tests/artifacts/perf/20260801T-parallel-edgelist-parse-cc/bench_edgelist.py \
    --role sweep --graph ca-AstroPh --reps 9 --out sweep.json
python3 tests/artifacts/perf/20260801T-parallel-edgelist-parse-cc/capstone.py \
    --graph facebook_combined --reps 8 --out capstone.json
```

Graphs are the SNAP originals; fetch with
`python3 scripts/parallel_analytics_pass.py --role fetch --graph-dir graphs`.

## Chooser statement

**Choose FrankenNetworkX when any single stage of your job takes more than about a second under
NetworkX.** At that size the stage is almost certainly one of the all-sources kernels — exact
betweenness, closeness, harmonic, eccentricity — and those are `|V|` independent passes that
NetworkX structurally cannot spread across cores: CPython's GIL serialises them, it ships no
thread pool or `n_jobs`, and the `multiprocessing` escape hatch requires pickling a dict-of-dict
adjacency into every worker. Measured here, that whole pass is **131.0 s under NetworkX and
0.105 s under fnx on a 4039-node graph**, and the prior artifact measured **50.7 minutes versus
4.7 seconds on an 18 772-node one**. NetworkX's cpu/wall was 1.00 on every stage of every
replicate; it never used a second core, because there is no way to ask it to.

**Stay on NetworkX for exploratory work on graphs of a few thousand edges**, where the whole pass
is already sub-second and its ecosystem, drawing, and generator breadth matter more than the
constant factor. The crossover is not about graph size in nodes — it is the moment a stage stops
being interactive, because that is the moment the missing capability starts costing you minutes
instead of milliseconds.
