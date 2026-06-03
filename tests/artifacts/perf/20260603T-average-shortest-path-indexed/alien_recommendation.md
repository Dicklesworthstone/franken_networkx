# Alien Graveyard Recommendation Card

## Target

`average_shortest_path_length(Graph)` in `crates/fnx-algorithms/src/lib.rs`.

## Symptom

Profiled all-sources BFS spends most samples below `get_index_of` and string
hash/equality while converting neighbor names back to integer node IDs.

## Harvested Primitive

Use the existing compact graph representation directly: replay CSR-like
integer adjacency (`neighbors_indices`) and reuse per-source traversal buffers.
This matches the graveyard guidance for avoiding string/object-heavy hot paths,
using compact graph representation, and improving cache-local traversal.

## Contract

- One lever: replace string-keyed neighbor lookup with integer adjacency in
  ASPL BFS.
- Fallback trigger: revert if golden ASPL output changes, disconnected behavior
  changes, or Criterion/harness speedup falls below Score 2.0.
- Proof obligations: node-index summation order, BFS adjacency order,
  disconnected `INFINITY`, final floating-point division, and checksum.
- Risk: low. The function exposes only an aggregate distance value, not paths.

## EV

EV = Impact 5 x Confidence 5 x Reuse 4 / Effort 2 x AdoptionFriction 1 = 50.

Proceed: shipped as `br-r37-c1-ga0ow`.
