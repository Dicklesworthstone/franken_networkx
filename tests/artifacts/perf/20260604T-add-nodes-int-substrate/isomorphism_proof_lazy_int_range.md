# Isomorphism proof: lazy integer range node keys

## Change

`PyGraph::_fast_add_int_nodes_range_stop` no longer fills `node_key_map` with
Python int objects for every `range(0, stop)` node. `PyGraph::py_node_key`
returns a Python int for bare canonical integers inside the recorded lazy range,
unless `node_key_map` already has a first-object winner.

## Preservation

- Ordering preserved: `inner.extend_nodes_unrecorded` receives the same
  canonical sequence `0, 1, ..., stop-1`; copy, `copy.copy`, constructor, and
  directed/multigraph conversion paths iterate `inner.nodes_ordered()`.
- Tie-breaking unchanged: `node_key_map` remains first-wins. Re-adding `0.0` or
  `False` after lazy `0` does not overwrite displayed `0`; removing and re-adding
  lets the new object win, matching dict semantics.
- Floating point: N/A for the optimized construction path. The proof includes
  numeric-equivalent `0`, `0.0`, and `False` membership/display checks.
- RNG: N/A.
- Golden outputs: artifact SHA check passed for final benchmark and semantic
  golden output.

## Golden evidence

- Bead digest stayed
  `eae2ed4eadc93d3264aef2fb5cd05bce54b2c934b5805383f8e5ad4113505b75`.
- Semantic golden SHA:
  `921f5a1b6ef8883e84c1eb66f50ed6c82aac313b87741d789a6326c174834410`.
- `sha256sum -c lazy_int_range_sha256.txt` passed.

