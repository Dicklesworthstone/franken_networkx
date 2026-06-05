# fix: mycielskian node relabeling + edge order parity with networkx

## Bugs (two)
1. NODE LABELS: networkx's mycielskian does `convert_node_labels_to_integers(G)`
   first, so output nodes are integers 0..2n. fnx kept the original labels for the
   base copy (e.g. ['a','b','c',3,4,5,6] vs nx [0,1,2,3,4,5,6]) — a real divergence
   for any non-integer-labeled base graph.
2. EDGE ORDER: nx adds the Mycielski shadow edges in TWO passes — all `(u, v+n)`
   for the old edges, then all `(u+n, v)`. fnx interleaved both per edge
   (`add_edge(n+i, v); add_edge(n+j, u)`), diverging on edge order even for
   integer-labeled graphs (e.g. node 1's neighbors [2,7,5] in nx vs [2,5,7]).

## Fix
Reimplement to mirror nx exactly: relabel to integers once via
`convert_node_labels_to_integers` (fnx's matches nx — verified), then per
iteration re-add old edges (attrs preserved), add shadow nodes n..2n-1, add
`(u, v+n)` for all old edges, then `(u+n, v)` for all old edges, then apex 2n and
shadow->apex edges. node_to_idx is no longer needed (labels are 0..n-1 indices).

## Proof
parity_proof.py: 38 cases — mycielskian on int/string/mixed bases x iterations
0..3, plus mycielski_graph(1..6) — comparing full node order, edge order, node
attrs, and error parity vs networkx. 0 mismatches.
golden_sha256 (over nx output, now matched by fnx):
0107616cccd312a5f5add2565515fce035126565296085a7301b951bcb9cd32d.

Pure-Python behavior-parity fix (no Rust change; mycielskian doesn't use the Rust
kernel). NOTE: full pytest collection currently blocked by an unrelated
maturin/.so rebuild failure in TealSpring's in-flight Rust (fnx-algorithms),
so validation is via the direct nx differential above.
