# DiGraph Exact-Int Attributed Batch Collector Rejection

Bead: `br-r37-c1-04z53.84`

## Target

After `br-r37-c1-04z53.82`, the focused DiGraph attributed construction fixture
still showed native `_try_add_edges_from_batch` as the residual:

- Fixture: 2000 nodes, 8000 seeded random directed edge tuples, each with
  `{"weight": 1.0}`.
- Baseline FNX direct median: `0.021087792003527284s`.
- Baseline FNX direct mean: `0.021590931089700793s`.
- Baseline NetworkX direct median: `0.006498498987639323s`.
- Baseline ratio: FNX was `3.245025050190512x` slower than NetworkX.
- Baseline hyperfine FNX mean: `0.8801893567200002s` for 30 constructions.
- Baseline cProfile: `_try_add_edges_from_batch` consumed `1.701s` over 100
  constructions.

## One Lever Tried

`PyDiGraph::add_attr_edge_batch` was changed to route list/tuple inputs through a
fresh-graph exact-integer endpoint collector before falling back to the generic
attributed edge collector. The attempted fast path targeted the profile-visible
canonicalization and display-conflict checks for the common `int` node fixture.

## Result

- Candidate FNX direct median: `0.03898717099218629s`.
- Candidate FNX direct mean: `0.03794105109144849s`.
- Direct median speedup: `0.5408905408333845x` (regression).
- Direct mean speedup: `0.5690651805523427x` (regression).
- Candidate was rejected before hyperfine/profile escalation because the direct
  rerun failed the keep threshold decisively.

## Golden Proof

- Ordered construction digest:
  `e603205862fdf5e9ed648d992331f9f236208d0d0bb5743ab01a1103a678c144`.
- Node-attribute semantic digest:
  `334a1d40c776f5539620631bb1564c19a8cb7f5b5187bc120784808a2a264bd3`.
- Both candidate digests matched NetworkX.

## Verdict

Rejected. Source was reverted; no runtime change is kept. This is the second
failed attributed-batch micro-lever after the `dict.copy()` mirror experiment, so
the next pass should pivot to a different primitive rather than another collector
or mirror-copy specialization.
