# NEGATIVE EVIDENCE — compose(MultiGraph) native keyed-batch does NOT help (materialization-bound)

- Agent: `BlackThrush` · 2026-06-21 · (no code change — reverted)

## What was tried
Added the symmetric `_native_add_keyed_edges_with_data` to PyMultiGraph (undirected sibling
of the MultiDiGraph one that won compose 0.36x->0.67x, 5a13d1e37). compose already routes
via getattr, so it auto-applied.

## Why REVERTED (~0-gain / slight regression)
compose(MultiGraph) 0.53x -> 0.48x (got SLOWER). Root cause: compose is NOT add-bound for
the undirected case, it is edge_map-MATERIALIZATION bound. The Python pre-merge loop
`for u,v,key,d in G.edges(keys=True, data=True): em[(u,v,key)] = dict(d)` (+ H) costs
27.79ms on its own — ~= nx's ENTIRE compose (29ms). The native batch only optimizes the
inner edge insert (already a small fraction), and its per-edge collect overhead
(node_key_to_string + edge_key_lookup + canonical pair + batch_display_conflict) slightly
EXCEEDS the per-edge add it replaces. Byte-exact 3000/3000 but no speed win, so reverted.
(MultiDiGraph differs: its per-edge add_edge_with_key_and_attrs on succ+pred was genuinely
the bottleneck, hence the batch helped there.)

## The real lever (scoped)
The shared bottleneck for BOTH MG and MD compose is the Python `edges(keys=True,data=True)`
attr-view materialization + `dict(d)` per edge. To dominate, a fully-native `_native_compose`
must read node_py_attrs / edge_py_attrs DIRECTLY from G's and H's Rust storage (cloning the
stored dicts, H-wins merge on shared (u,v,key)), skipping the Python edge view entirely —
the data-carrying sibling of `_native_difference` (which is data-free). Substantial +
correctness-sensitive (node/edge attr merge, order, undirected canonical orientation);
scoped for a fresh session. MultiDiGraph compose stays the committed 0.60-0.67x win.
