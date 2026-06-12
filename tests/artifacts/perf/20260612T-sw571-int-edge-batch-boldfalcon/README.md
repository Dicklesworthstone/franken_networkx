# br-r37-c1-sw571 Evidence

Target: `empty_graph(n)` followed by exact-int `Graph.add_edges_from`.

Baseline source: `ce615d5f31ae17bba066a13e1e34b19ae3b59760`

Lever: route list/tuple batches of exact `int` endpoints on existing contiguous integer nodes through an index-space insertion path, falling back before mutation for bool, float, tuple, missing-node, attr, generator, or non-prefix cases.

## Behavior Proof

- Golden payload SHA before: `8522db256b917d8703409680cf3752175432a550c8172fcab3e5afba0117b7a1`
- Golden payload SHA after: `8522db256b917d8703409680cf3752175432a550c8172fcab3e5afba0117b7a1`
- Pretty JSON file SHA before/after: `662f8740bebdc87870c041de12044dba211b5829906d17a1b788e11c0c74e5d6`
- `cmp baseline_golden.json candidate_golden.json`: byte-identical

The golden covers node order, edge order, adjacency row order, degree sequence, partial-error mutation prefix, bool/float/tuple endpoint fallbacks, missing-node fallback, attr fallback, generator input fallback, and seeded `random_regular_graph` output.

## Timing

- Direct loop mean: `0.0056515566s -> 0.0017460271s` (`3.24x`)
- Direct loop median: `0.0055094115s -> 0.0016680255s` (`3.30x`)
- Hyperfine process mean, 20 repeats: `0.3962154328s -> 0.2996849166s` (`1.32x`)
- Baseline profile: `_try_add_edges_from_batch` `1.102s / 200` calls
- Candidate profile: `_try_add_edges_from_batch` `0.274s / 200` calls

Score: Impact `3`, Confidence `3`, Effort `2` -> `4.5`, keep.
