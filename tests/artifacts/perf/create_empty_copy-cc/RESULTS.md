# create_empty_copy — native attr-presence gate + key-only clone

## Lever
create_empty_copy built ``list((node, dict(attrs)) for node, attrs in
G.nodes(data=True))`` and fed it to add_nodes_from's per-node Python add_node
loop. Profiling: ``list(G.nodes(data=True))`` alone is ~0.5ms@n=1500 (per-node
attr-dict reconstruction from Rust) — the entire cost. Two facts unlock it:
(1) add_nodes_from copies attr-dict CONTENTS into a fresh node dict (verified —
never aliases G's), so the explicit ``dict(attrs)`` was redundant; (2) the native
``_fnx.graph_has_any_attrs`` check (~0.08us) proves whether ANY node/edge carries
a Python-visible attr. When it's False (the common algorithm-graph case), an
empty copy is just the node KEYS — ``_native_node_keys()`` returns them nearly
free and feeds the bulk int-node fast path. graph-level attrs copied separately.

## Correctness (byte-exact)
80 comparisons across simple-int / node-attrs / str-nodes / directed / multigraph
x with_data {True,False}: node+attr+graph-attr+edge signature identical to nx,
0 mismatches. golden sha 39d96fe33db6c6ac. Verified no aliasing (mutating the
copy's node attr leaves G untouched). 591 create_empty_copy-referencing tests pass
(3 pre-existing unrelated classification/coverage failures).

## Benchmark (warm min, interleaved before/after) — ratio = nx/fnx
| graph     | BEFORE fnx       | AFTER fnx        | self-speedup |
|-----------|------------------|------------------|--------------|
| BA(400)   | 0.639ms (0.33x)  | 0.094ms (2.23x)  | 6.8x         |
| BA(1500)  | 2.389ms (0.35x)  | 0.342ms (2.35x)  | 7.0x         |

fnx flipped from ~3x SLOWER than nx to 2.2-2.4x FASTER, ~7x self-speedup.
