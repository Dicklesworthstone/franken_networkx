# Alien/No-Gaps Note

## Applied Primitive

The kept lever is a zero-payload specialization: when the copied edge payload is empty, represent the edge as the minimal `(u, v)` record instead of carrying an explicit empty payload through the generic attributed-edge path.

This matches the no-gaps performance campaign constraint:

- Pure Python/Rust project code only; no C BLAS, MKL, XLA, or linked native dependency.
- One optimization lever.
- Profile-backed target.
- Behavior proof and golden digest before keeping.

## Harvest Source

Relevant pattern from the alien-graveyard pass: avoid redundant payload materialization on hot bulk-transfer paths, especially when a stable fast path already exists for the payload-free representation.

The artifact coding step here was to translate that primitive into the existing NetworkX-compatible graph API:

- Keep full attributed behavior for non-empty data.
- Keep fallback behavior for non-string attribute keys.
- Use the existing `Graph.add_edges_from` plain-edge fast path for the empty-data majority case.

## Next Primitive Candidate

After this pass, re-profile `ego_graph` before proposing another lever. The current after-profile shows remaining time in:

- `EdgeDataView._materialize()`
- node attribute copy via `add_node`
- neighbor traversal during ego-node discovery

Do not optimize any of those until a fresh ready bead or fresh profile establishes the next top residual target.
