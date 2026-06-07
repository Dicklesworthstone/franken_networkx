# ctor lever 1: native edge-list validation pass (d58s8)

## What moved
Python __init__ validation: 24ms -> ~1ms per 5 calls (cProfile).
The per-item Python walk (isinstance x10/edge, hasattr, len) became ONE
native pass; the post-absorb hashability NodeIterator walk folded into
the same pass (incl. the subtle old behavior: non-multi 3-tuples with
unhashable NON-DICT third elements — the __new__ mis-absorb case —
pinned by test_ctor_wraps_unhashable_in_edge_list_error).

## What didn't (and why that's the finding)
Wall: 26.4ms vs nx 6.9ms = still ~3.8x. The Python layer was peeled
clean off; the remaining ~25ms is ENTIRELY the Rust __new__ per-edge
absorb — the 71x9k construction tax (add_edge_impl dual-record, eager
mirrors), now ISOLATED with no Python noise on top.

## Next lever (specified): route __new__ ingestion through the d58s8
bulk machinery — validated list -> node/edge batches -> extends with
fresh ledger + lazy mirrors (the exact l5ve7/tree-tier recipe, applied
to the constructor itself). Target: ctor 3.8x -> ~1.5x or better.

## Contract battery: 44 cases x 4 classes (sha 30b52f6c)
tuples/lists/mixed/sets/ranges/scalars/long/4-nondict/empty/unhashable
u/v/third. Pre-existing str-items divergence FILED as ewtd1 (nx accepts
['ab','cd'] as 2-char edge specs).
