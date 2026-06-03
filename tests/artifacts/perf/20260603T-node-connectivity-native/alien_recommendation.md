# br-r37-c1-w3yng alien recommendation card

## Selected primitive

Graph-invariant residual template reuse for repeated local max-flow probes.

## Contract

- Input: a fixed simple undirected graph passed to global `node_connectivity`.
- Artifact: one node-split residual template with the same nodes, directed split edges, reverse residual edges, and capacities as a fresh per-pair build.
- Runtime rule: clone the template per `(source, sink)` pair, then run the existing `aux_max_flow` unchanged.
- Exhaustion behavior: unchanged; the max-flow loop still stops only when no augmenting path exists.

## EV score

- Impact: 3
- Confidence: 3
- Reuse: 3
- Effort: 1
- Adoption friction: 1
- EV: `27.0`

## Failure risks and guards

- Risk: accidentally sharing mutable residual state across pairs.
- Guard: clone before `aux_max_flow`; the template is never passed mutably.
- Risk: hidden ordering drift.
- Guard: pair order and sorted residual neighbor traversal are unchanged; golden digest is unchanged.
- Risk: optimizing the undirected path while the bead names DiGraph.
- Guard: record the non-reproduced DiGraph sweep and immediately reprofile directed pair-ordering/max-flow in the next pass.
