# Isomorphism Proof

## Change

`quotient_graph` now derives default block-node metrics from partition-local
edge counts and returns the directly constructed fnx result when
`create_using is None`.

## Ordering

Preserved.

- Partition order is unchanged.
- Block labels remain the original `frozenset` blocks unless `relabel=True`.
- Default node attr insertion order remains `graph`, `nnodes`, `nedges`,
  `density`.
- Default simple-undirected quotient edge emission still iterates block pairs in
  ascending partition order.

## Tie-Breaking

Unchanged.

- No graph algorithm tie-break policy changed.
- Cross-block default edge order still follows block-pair order, not hash order.
- Custom `edge_relation`, custom `edge_data`, `create_using`, directed, and
  multigraph edge construction stay on existing fallback paths.

## Floating Point

Preserved for this path.

- Density uses the same formula as the local `density` helper:
  `m / (n * (n - 1))`, doubled for undirected graphs.
- Empty or singleton blocks still return integer `0`, matching the prior helper.
- Non-integer cross-block weights still fall back to the previous summing path.

## RNG

Unchanged. The benchmark graph seed remains `12345`; no runtime RNG behavior was
changed.

## Graph Attribute

Preserved.

- The `graph` node attribute remains `G.subgraph(block)`.
- The manual validator confirms both FNX and NetworkX expose a live subgraph
  object while scalar `nedges` remains the creation-time count.

## Golden Output

FNX baseline, NetworkX baseline, FNX after, and NetworkX after all match:

`3b82f51eccda8bd9a2f0a24657abf67f8bb2bc9b9da8e49d136f6089b31be62a`

The artifact pack is covered by `artifact_sha256.txt` and verified by
`artifact_sha256_check.txt`.
