# br-r37-c1-tlfqe Isomorphism Proof

The committed lever changes only the internal insertion strategy for
`Graph::extend_edges_unrecorded`. It does not change the public Python
validation path, the edge iterator contract, or observable graph semantics.

## Ordering

- Input edge iteration order is unchanged: the loop still consumes the supplied
  iterator exactly once from left to right.
- Node insertion order remains first-seen endpoint order. For each edge, the
  left endpoint is inserted before the right endpoint when both are new.
- Edge insertion order remains the first occurrence of each undirected edge.
  Duplicate edges are skipped after the same canonical `EdgeKeyRef` lookup.
- Self-loops still create one edge and one node, and do not create a second
  integer-neighbor entry for the same endpoint.

## Tie-breaking

NetworkX-visible tie-breaking for this path depends on node and edge insertion
order. Those orders are preserved by the one-pass index lookup described above.
No algorithmic tie-break policy is changed.

## Floating Point and RNG

This path constructs graph topology only. It performs no floating-point
arithmetic and uses no random number generation.

## Golden Output

- Construction digest before and after:
  `74d9d20a476a21a81c3d7643eda931baea4788d9968cc125f6e30425842e990c`
- Valid-batch semantic golden: `plain_edges_valid_semantics_golden.jsonl`
- Semantic record SHA inside golden:
  `5292897ebe38988d2726c7bc6f161cde170c89bc08b00bfe51bb432ac0d8b5d3`
- Artifact sha check:
  `sha256sum -c plain_edges_classes_prealloc_sha256.txt`

The valid-batch golden compares FrankenNetworkX and NetworkX for node order,
edge order, `edges(data=True)` shape, degree, and edge count across path,
duplicate, self-loop, hash-equal, string, tuple, and float-node cases.

The known malformed-edge partial-progress parity bug is tracked separately as
`br-r37-c1-77ux3`. This lever does not touch that validation/error-order path.

