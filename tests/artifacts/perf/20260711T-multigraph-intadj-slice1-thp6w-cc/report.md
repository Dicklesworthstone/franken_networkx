# br-r37-c1-thp6w Slice 1 — MultiGraph lazy integer-adjacency memo

Status: **SHIP (infrastructure, no perf claim).** Byte-identical; 74/74 suite green; clippy clean.

## What

First slice of the MultiGraph integer-adjacency epoch. Adds a lazy, revision-keyed integer
adjacency memo to `MultiGraph` and a `with_int_adjacency(|adj| ...)` accessor — the foundation
Slice 2 routes hot ops through. NOT a perf win by itself (no production caller yet).

## Design (safe by construction)

- `IntAdjCache(RwLock<Option<(u64, Vec<Vec<usize>>)>>)` field; `with_int_adjacency` builds the
  integer rows from the authoritative String `adjacency` on first read, memoized until mutation.
  Same pattern as `Graph::all_int_cache`.
- ZERO per-mutation maintenance (so no construction regression, unlike an eager 13-site mirror):
  auto-invalidated by the 14 existing `revision` bumps on content changes + ONE explicit clear in
  `apply_row_orders` (the only order-only mutator that skips `revision`).
- Fresh-per-clone memo (`IntAdjCache::clone` -> empty) — never Arc-shared across clones.

## Byte-identical

`with_int_adjacency` has NO production caller (inert), so it cannot change observable behavior;
the full fnx-classes suite passing unchanged (74/74) proves zero regression. Two invariant tests
prove the memo mirrors the String adjacency exactly across add_node / add_edge / parallel /
remove_edge / remove_node (renumber) / reorder / clear_edges (read-mutate-read catches any
un-invalidated path) and across clone.

## Gate

- `cargo test --release -p fnx-classes --lib`: 74 passed, 0 failed (see validation.log).
- `cargo clippy --release -p fnx-classes --lib --tests -- -D warnings`: clean.

## Slice 2 (next, the win)

Route the bidirectional-dijkstra MultiGraph residual + mg edge/degree reads through
`with_int_adjacency` (profiled 100x+ on neighbor-traversal-bound ops). Before the FIRST production
reader, complete the order-mutator audit (memo order-correctness currently relies on
`apply_row_orders` being the only revision-skipping order change).
