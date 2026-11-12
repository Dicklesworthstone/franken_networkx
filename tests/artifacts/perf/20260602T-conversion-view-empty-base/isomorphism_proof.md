# Isomorphism proof: conversion-view empty base

Bead: `br-r37-c1-y2b8t`

## Lever

`_ConversionGraphViewBase.__new__` now calls `super().__new__(cls)` without the
source graph argument. This prevents the mixed PyO3 `Graph`/`DiGraph` base from
copying the parent graph into dead Rust storage. `__init__` still installs the
same `_graph`, `frozen`, node view, edge view, adjacency view, successor view,
predecessor view, and degree view fields.

No Rust kernel, graph mutation, RNG, or floating-point path changed.

## Baseline and after

Direct rch sample, `graph_to_directed`, `n=1000`, `degree=4`, `calls=50`:

- Old constructor shim: `0.02008656938s` per call.
- New empty-base constructor: `0.00000334412s` per call.
- Speedup: `6006.95x`.
- Upstream NetworkX reference: `0.00000948714s` per call.
- New fnx vs NetworkX: `2.84x` faster on the direct constructor sample.

Hyperfine rch process benchmark:

- Old constructor command mean: `1.3921046396s`.
- New constructor command mean: `0.3265879022s`.
- Speedup: `4.263x`.
- Upstream NetworkX command mean: `0.1581678336s`.

## Golden digests

Focused `graph_to_directed` snapshot digest:

- Old fnx: `ed98a168154b409394d776d61e5872bbed509f3e7e670cbc0867cf4f3161f9c8`.
- New fnx: `ed98a168154b409394d776d61e5872bbed509f3e7e670cbc0867cf4f3161f9c8`.
- NetworkX: `ed98a168154b409394d776d61e5872bbed509f3e7e670cbc0867cf4f3161f9c8`.

All fnx conversion cases snapshot digest:

- Old fnx: `f1de67a09a63fe69307aa7ab977b517ba5da5d1c610d91decdc865cd41bf71ee`.
- New fnx: `f1de67a09a63fe69307aa7ab977b517ba5da5d1c610d91decdc865cd41bf71ee`.

The all-case fnx proof covers:

- `Graph.to_directed(as_view=True)`.
- `DiGraph.to_undirected(as_view=True)`.
- `MultiGraph.to_directed(as_view=True)`.
- `MultiDiGraph.to_undirected(as_view=True)`.

## Observable behavior

Ordering:

- Node iteration order is delegated to the same source graph.
- Edge iteration order is delegated to the same conversion-view edge methods.
- `copy()` observes the same delegated edges and attributes.

Tie-breaking:

- No tie-breaking algorithm changed. The view constructor only changes empty
  base allocation; all query methods dispatch through the same Python view
  methods as before.

Floating point:

- No floating-point computation changed. Weighted degree and weighted size
  snapshots are byte-stable between old and new fnx.

RNG:

- No RNG path changed. Benchmark graph construction is deterministic.

Error classes and mutability:

- Frozen view mutators remain shadowed by `_ConversionGraphViewBase`.
- The constructor does not change null, missing-node, or edge-query exception
  routes; existing focused parity tests exercise these wrappers.

## Verification artifacts

- `baseline_fnx_old_graph_to_directed.json`
- `after_fnx_new_graph_to_directed.json`
- `baseline_nx_graph_to_directed.json`
- `golden_fnx_old_all_cases.json`
- `golden_fnx_new_all_cases.json`
- `golden_nx_all_cases.json`
- `hyperfine_graph_to_directed.json`
- `hyperfine_graph_to_directed.stdout`
