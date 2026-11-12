# br-r37-c1-wxy3x pass 2: greedy_modularity_communities raw-route rejection

Date: 2026-06-13
Worktree: `/data/projects/.scratch/franken_networkx-wxy3x-cnm-boldfalcon-20260613T0015`
HEAD: `89bde94ef6999334b3a543d8ae31508c1fe6cab8`

## Candidate

Route `franken_networkx.community.greedy_modularity_communities` to the existing
raw PyO3 binding for concrete simple `fnx.Graph` inputs, returning a
NetworkX-compatible `list[frozenset]`, and fall back for weighted, cutoff,
best_n, directed, multigraph, view, or edge-attribute cases.

## Baseline/profile

Release extension was installed into `/data/projects/franken_networkx/.venv` via:

```bash
VIRTUAL_ENV=/data/projects/franken_networkx/.venv PATH=/data/projects/franken_networkx/.venv/bin:$PATH rch exec -- maturin develop --release --features pyo3/abi3-py310
```

Hyperfine commands include Python startup and graph construction, but each command
performs repeated algorithm calls on one deterministic graph.

| Graph | Command | Mean | Per call |
| --- | --- | ---: | ---: |
| watts_strogatz_150 | fnx public, repeat 20 | 0.66972233942 s | 0.033486116971 s |
| watts_strogatz_150 | NetworkX, repeat 20 | 0.63525802352 s | 0.031762901176 s |
| watts_strogatz_150 | raw binding, repeat 20 | 0.28956050252 s | 0.014478025126 s |
| watts_strogatz_300 | fnx public, repeat 5 | 0.65477483170 s | 0.130954966340 s |
| watts_strogatz_300 | NetworkX, repeat 5 | 0.64169359270 s | 0.128338718540 s |
| watts_strogatz_300 | raw binding, repeat 5 | 0.30137380860 s | 0.060274761720 s |

cProfile top lines for ws150:

- fnx public: 20 calls in 0.872 s; `networkx.algorithms.community.modularity_max.greedy_modularity_communities` and `_greedy_modularity_communities_generator` dominate.
- NetworkX: 20 calls in 0.832 s; same NetworkX mapped-queue generator dominates.
- raw binding: 20 calls in 0.034 s; raw PyO3 call is 0.013 s total, fnx graph copy is 0.018 s total.

## Golden proof

Final proof file:

```text
e4446c0e162da1c2427beda5cd47f88ac9ea6a8e08c35005bd35d0e7ddb17b40  baseline_golden_v3.json
```

The corpus compares ordered normalized partitions and return surface types.
The raw route fails the behavior gate:

| Case | Raw ordered match | Raw unordered partition match | NX count | Raw count |
| --- | --- | --- | ---: | ---: |
| barbell_5_1 | true | true | 2 | 2 |
| karate | false | true | 3 | 3 |
| watts_strogatz_150 | false | true | 7 | 7 |
| watts_strogatz_300 | false | false | 5 | 6 |
| path_12 | false | true | 3 | 3 |
| cycle_18 | false | true | 4 | 4 |
| complete_9 | true | true | 1 | 1 |
| disconnected_components | false | true | 2 | 2 |
| zero_edge_7 | true | true | 7 | 7 |

The weighted guard fixture confirms parity fallback can preserve both default
unweighted and explicit weighted NetworkX behavior through
`_networkx_graph_for_parity`, while raw explicit weighted output has NetworkX-
visible ordering divergence.

## Decision

Reject the production routing lever for this pass.

Opportunity score before proof: Impact 4, confidence 4, effort 1 => 16.0.
Behavior gate result: fail, so keep score is 0 and production source must not
change.

## Next primitive

Fix the Rust CNM kernel semantics before attempting a Python wrapper route:

1. Replicate NetworkX's CNM merge ordering and final community ordering exactly.
2. Add Rust/Python golden coverage for path, cycle, disconnected components,
   karate, watts_strogatz_150, and watts_strogatz_300.
3. Re-run this wrapper routing pass only after the raw kernel matches ordered
   normalized partitions and return surface for the guarded cases.
