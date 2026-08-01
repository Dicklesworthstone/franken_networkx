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

## Measurement note

`triangles` is reported **cold — one freshly-read graph per call**. Measured warm inside a loop
that had already called `clustering()`, it reports 0.23 ms and 1076x, but that is a hit on the
census cache shared across the family (`bd568297a`), not the kernel. The cold numbers above are
the honest ones; the tell was cpu/wall ~1.0 on a kernel that should be fanning out.

Host `thinkstation1`, 32 physical / 64 SMT, load 12–23 (shared box, peers active), NetworkX 3.6.1
live in-process, 7 replicates, median reported.
