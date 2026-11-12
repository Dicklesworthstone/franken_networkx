# DiGraph Attributed Edge Mirror Dict Copy Rejection

Bead: `br-r37-c1-04z53.83`

## Target

After `br-r37-c1-04z53.82`, the focused DiGraph attributed construction fixture
still showed native `_try_add_edges_from_batch` as the residual:

- Fixture: 2000 nodes, 8000 seeded random directed edge tuples, each with
  `{"weight": 1.0}`.
- Baseline FNX direct median: `0.021087792003527284s`.
- Baseline NetworkX direct median: `0.006498498987639323s`.
- Baseline ratio: FNX was `3.245025050190512x` slower than NetworkX.
- Baseline hyperfine FNX mean: `0.8801893567200002s` for 30 constructions.
- Baseline cProfile: `_try_add_edges_from_batch` consumed `1.701s` over 100
  constructions.

## One Lever Tried

`py_dict_to_attr_map_with_mirror` was changed to build the Python edge-attribute
mirror with `PyDict.copy()` instead of allocating a fresh `PyDict` and inserting
each key/value manually. The Rust `AttrMap` conversion loop was otherwise
unchanged, preserving the existing eager mirror semantics.

## Result

- Candidate FNX direct median: `0.021969221998006105s`.
- Candidate FNX direct mean: `0.02274912027695047s`.
- Direct median speedup: `0.9598788707875582x` (regression).
- Direct mean speedup: `0.9490886164761649x` (regression).
- Candidate was rejected before hyperfine/profile escalation because the direct
  rerun already failed the keep threshold.

## Golden Proof

- Ordered construction digest:
  `e603205862fdf5e9ed648d992331f9f236208d0d0bb5743ab01a1103a678c144`.
- Node-attribute semantic digest:
  `334a1d40c776f5539620631bb1564c19a8cb7f5b5187bc120784808a2a264bd3`.
- Both candidate digests matched NetworkX.

## Verdict

Rejected. Source was reverted; no runtime change is kept. The next pass should
pivot away from mirror-copy micro-levers and attack a deeper attributed-batch
primitive.
