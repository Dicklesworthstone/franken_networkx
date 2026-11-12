# ctor absorb lever 3: index-pair edge batches — REJECTED (wash)

## Hypothesis
Post edges-map flip, the absorb's edge batch carried 2 owned Strings
per edge (~24k clones @12k edges, most wasted on existing nodes).
Two-pass index batching (canonical->idx local map, new
extend_edges_by_indices_unrecorded, zero Strings in the edge stream)
should close ctor 1.31x toward 1.0x.

## Result: same-window A/B (stash discipline)
OLD absorb 10.05ms vs NEW 10.22ms — WASH. Implementation was correct
(full battery sha 12ae595a + full pytest 21819 green before revert).

## Lesson
The String clones are NOT the post-flip absorb cost. The dominating
layer is PyO3 per-item extraction (PyIterator protocol + PyTuple
get_item + node_key_to_string conversions) — the local_idx HashMap ops
the lever ADDED roughly cancelled the clone savings. NEXT ctor lever
candidates (measure first): downcast PyList + positional get_item
(skip the iterator protocol); batch node_key_to_string for exact-int
runs via itoa; or accept the absorb at the PyO3 boundary and revisit
after the Multi flips. Patch archived for reuse if a future caller
wants extend_edges_by_indices (it was REVERTED with the lever — no
unused scaffolding).
