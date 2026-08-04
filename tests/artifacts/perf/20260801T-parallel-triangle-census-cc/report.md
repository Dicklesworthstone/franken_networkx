# Parallel triangle census — widening the fan-out to the clustering family (cc, 2026-08-01)

Status: **kernel change.** The shared `u < v < w` triangle census now fans out over the rayon
pool in all three kernels that own one. **Bit-exact** against the pre-change build on every
output of every staged graph.

| graph | call | before | after | cpu/wall | vs live nx 3.6.1 |
|---|---|--:|--:|--:|--:|
| `facebook_combined` | `average_clustering` | 13.90 ms | **3.84 ms** | 14.89 | 92.4x → **317.1x** |
| `facebook_combined` | `transitivity` | 5.42 ms | **1.56 ms** | 26.97 | 230.0x → **784.9x** |
| `facebook_combined` | `triangles` (cold) | — | 5.37 ms | 11.29 | **47.0x** |
| `ca-AstroPh` | `average_clustering` | 39.30 ms | **11.09 ms** | 7.43 | 67.3x → **179.1x** |
| `ca-AstroPh` | `transitivity` | 19.96 ms | **3.91 ms** | 15.79 | 98.9x → **494.6x** |
| `ca-AstroPh` | `triangles` (cold) | — | 17.86 ms | 5.68 | **22.8x** |

## Why this target

After the edge-list parser landed
(`tests/artifacts/perf/20260801T-parallel-edgelist-parse-cc/`), re-profiling the whole analytics
job left `average_clustering` as the largest remaining stage still running at **cpu/wall ~1.06 —
fully serial** — while `betweenness_exact` and `closeness` beside it ran at 40.4 and 23.2. A
per-node triangle census is `|V|` independent neighbourhood intersections: embarrassingly
parallel, and unavailable to NetworkX for the same structural reason as every other parallel
kernel here — its census is a Python loop under the GIL.

The census is already shared across the clustering family, so one fix widens to
`clustering`, `average_clustering`, `transitivity` and `triangles`.

## Why it is bit-exact, not merely close

The census accumulates **integers**. Integer addition is associative and exact, so splitting the
`u` range across workers and summing the per-worker count vectors cannot change the total —
unlike a float reduction, which would have to preserve summation order.

Only the census fans out. `scores` and `average_clustering` are still built in node-index order
by the original serial loop, so the **f64 summation order that defines the public value is
untouched**. `transitivity` accumulates one integer and divides once at the end, seeing identical
operands. This is the same discipline as
[the scatter→gather lever](../../../../README.md): change which core does the arithmetic, never
the order it happens in.

Three kernels were converted, each with its inner loop split into a `#[inline]` per-node helper so
the serial and fanned-out paths run byte-identical logic:

* `clustering_coefficient` → `clustering_census_node`
* `transitivity` → `transitivity_census_node`
* `triangles` → `triangles_census_node`

`triangles` deliberately keeps a *different* helper rather than reusing the clustering one: it
marks the full neighbour row (self-loops included) and counts `edges_scanned` per `u < v` edge
rather than per triangle, which is the witness contract it has always reported.

Fan-out is gated on the existing `CENTRALITY_PARALLEL_THRESHOLD` (500 nodes), and the worker count
is capped so per-worker scratch (one count vector + one mark array per worker) stays under
~256 MB on very large graphs.

## Correctness

* **Bit-exactness harness**: `average_clustering`, `transitivity`, a SHA-256 over the full
  per-node `clustering()` map, and a SHA-256 over the full `triangles()` map, captured from the
  pre-change build and re-checked after. **All 4 outputs identical on all 3 staged SNAP graphs**
  (`facebook_combined`, `ca-CondMat`, `ca-AstroPh`).
* `cargo test -p fnx-algorithms` — **962 passed, 0 failed**.
* `pytest tests/python` — **49 941 passed**, 1065 skipped; the 7 `test_coverage_gaps.py` failures
  are environmental (the coverage generator spawns a subprocess whose interpreter has no
  `networkx`) and are identical to the pre-change baseline.

## Whole job, on this binary — `facebook_combined`, 8 interleaved replicates, live nx 3.6.1

Run at a genuinely quiet load (5.68 → 2.68), unlike the earlier passes in this session.

| stage | nx wall | nx cpu/wall | fnx wall | fnx cpu/wall | fnx threads | speedup |
|---|--:|--:|--:|--:|--:|--:|
| read_edgelist | 0.120 s | 1.02 | 0.0143 s | 1.19 | 1 | 8.4x |
| remove_self_loops | 0.000 s | 8.37 | 0.0001 s | 26.73 | 1 | 2.9x |
| connected_components | 0.008 s | 1.32 | 0.0006 s | 4.08 | 1 | 12.9x |
| degree_assortativity | 0.116 s | 1.02 | 0.0005 s | 5.86 | 1 | 226.1x |
| **average_clustering** | 1.228 s | 1.00 | **0.0036 s** | **16.81** | **65** | **341.7x** |
| core_number | 0.077 s | 1.04 | 0.0014 s | 2.68 | 1 | 53.9x |
| pagerank | 0.069 s | 1.04 | 0.0036 s | 1.67 | 1 | 19.3x |
| betweenness_exact | 78.855 s | 1.00 | 0.0573 s | 44.10 | 65 | 1377.1x |
| closeness | 24.710 s | 1.00 | 0.0046 s | 29.61 | 65 | 5379.9x |
| **TOTAL** | **105.436 s** | **1.00** | **0.0869 s** | **31.56** | **65** | **1212.9x** |

Median of the eight per-replicate ratios: **1208.5x**, CI **[1159.7, 1237.9]**.
`average_clustering` is the visible change: **cpu/wall 1.17 on one thread before, 16.81 on 65
after**. Whole-job cpu/wall rose 25.34 → 31.56.

The headline ratio did **not** rise despite fnx getting faster (0.105 s → 0.087 s), because the
same quieter box also sped the nx arm up (131.0 s → 105.4 s). A ratio is a joint measurement of
both arms; that is exactly why the arms are interleaved and why absolute walls are reported
alongside it rather than the ratio alone.

`degree_assortativity` still differs between engines by 2 ULP
(`0.06357722918564918` vs `...943`). That is pre-existing float-summation order in the
assortativity kernel — the 2026-07-30 study JSON already contains both values, and rebuilding
fnx's graph as a native `nx.Graph` and running nx's own kernel returns nx's value exactly. Every
other digest key matches, including the top-10 lists for pagerank, betweenness and closeness.

## Measurement note

`triangles` is reported **cold — one freshly-read graph per call**. Measured warm inside a loop
that had already called `clustering()`, it reports 0.23 ms and 1076x, but that is a hit on the
census cache shared across the family (`bd568297a`), not the kernel. The cold numbers above are
the honest ones; the tell was cpu/wall ~1.0 on a kernel that should be fanning out.

Host `thinkstation1`, 32 physical / 64 SMT, load 12–23 (shared box, peers active), NetworkX 3.6.1
live in-process, 7 replicates, median reported.
