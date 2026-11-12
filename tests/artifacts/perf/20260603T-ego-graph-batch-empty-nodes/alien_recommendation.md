# Alien recommendation: ego_graph batch empty node copy

## Harvested primitive

The alien-graveyard match was "constants kill you" plus vectorized/batched
execution: when a hot path repeatedly crosses the same small Python/Rust wrapper
boundary with empty payloads, batch the payload-free operation and preserve the
general attributed path as fallback.

## Application

`ego_graph(Graph, 0, radius=2)` on BA(3000, 4, seed=42) still spends visible
time in result construction after earlier edge-copy optimizations. The proposed
artifact was a zero-payload node-copy specialization:

- If every copied ego node has empty attrs, call `graph.add_nodes_from(ordered_nodes)`.
- If any copied node has attrs, keep the exact existing per-node
  `graph.add_node(node, **dict(G.nodes[node]))` loop.

## Decision

Rejected. The operation sample improved, but process-level hyperfine regressed
twice and failed the required confirmation gate.
