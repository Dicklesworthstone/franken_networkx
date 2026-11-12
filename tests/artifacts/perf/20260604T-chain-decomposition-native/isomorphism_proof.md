# Isomorphism proof

Change: replace the old Rust back-edge heuristic with the NetworkX
DFS-labeled-edge cycle-forest algorithm and route plain FNX `Graph`
`chain_decomposition` through the existing native binding.

Behavior preservation:

- Directed and multigraph rejection remains eager in the Python wrapper, before
  generator creation, with the same `NetworkXNotImplemented` type and wording.
- Missing root behavior remains lazy: the wrapper returns a generator, and
  iteration raises `NodeNotFound("Root node 99 is not in graph")`, matching
  NetworkX.
- Ordering is preserved by mirroring NetworkX `dfs_labeled_edges`: roots use
  graph insertion order, neighbors use adjacency insertion order, tree edges are
  oriented toward the DFS root, and nontree edges are emitted only when the
  opposite orientation has not already been inserted into the cycle forest.
- Tie-breaking is graph insertion order only; no sorting or hash-order walk was
  introduced.
- Floating point is not involved.
- RNG is not involved.
- Output payload SHA-256 before and after:
  `4929d2c6d3c2bbdba133dcebf95c08db9f066bb46e5af63428e1be7e9528c84e`.

Regression coverage:

- Rust unit tests cover triangle order, disconnected component traversal with
  root limiting, and self-loop chain output.
- Python focused parity tests cover module re-export parity plus eager
  directed/multigraph rejection.
- Benchmark golden sweep reports `digests_match: true` against NetworkX.
