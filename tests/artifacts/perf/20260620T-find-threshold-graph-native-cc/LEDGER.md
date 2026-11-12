# Perf lever (code-only, bench deferred) — find_threshold_graph routed to native threshold_graph (br-r37-c1-threshnative)

- Agent: `BlackThrush` · 2026-06-20 · File: `python/franken_networkx/threshold.py`
- DISK-LOW turn: code-only, no build/bench. Parity verified with existing install.

nx's `find_threshold_graph(G, create_using)` is exactly
`threshold_graph(find_creation_sequence(G), create_using)`. The fnx override
delegated the WHOLE thing to nx then `_from_nx_graph`-converted. Now: run nx's
creation-sequence finder (O(V) degree scan, unchanged — same as the delegated path
already did internally), then route the O(V^2) construction through THIS module's
native `threshold_graph` (batched add_edges_from, no intermediate nx graph + no
conversion). The O(V^2) build dominates the O(V) scan, so the saved nx-build +
conversion is the win.

## Parity (existing install, no build)

1500 random graphs: find_threshold_graph byte-exact (node order, edge order, graph
attrs, returns fnx.Graph); error contract matches. 0 mismatches.

## Perf

BENCH DEFERRED (disk-low). Confident win (the O(V^2) nx threshold build + conversion
is replaced by the native batched build). Measure when disk recovers, together with
threshold_graph (br-r37-c1-threshnative) and from_prufer_sequence.
