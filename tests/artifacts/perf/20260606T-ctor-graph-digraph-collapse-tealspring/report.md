# br-r37-c1-o0w3a rejection: Graph(DiGraph) native collapse

## Target

Replace the Python `Graph(DiGraph)` rebuild with a native directed-to-undirected
collapse while preserving NetworkX node order, adjacency row order, edge attr
winner semantics, graph attrs, and shallow-copy independence.

## Proof

- Golden SHA stayed unchanged:
  `81ae2a2f9f60cb4e9a1accc742704cb483fdb9bb04c4419433b3b79b06dbf957`.
- Focused constructor parity passed: `11 passed`.

## Performance Result

Rejected. The lever did not clear the keep gate.

- Baseline hyperfine: `1.664s +/- 0.098s`.
- After hyperfine: `1.622s +/- 0.039s`, only about `1.03x`.
- Recheck direct timings were mixed or worse:
  - `graph_digraph_800_3200`: FNX remained about `4.17x-5.22x` vs NX.
  - `graph_digraph_3000_12000`: FNX remained about `3.39x-5.02x` vs NX.
- One rch hyperfine recheck aborted with exit `135`.

## Decision

Source fast-path hunks were removed. The next attempt should attack a deeper
attribute/state substrate instead of this shallow absorb shape.
