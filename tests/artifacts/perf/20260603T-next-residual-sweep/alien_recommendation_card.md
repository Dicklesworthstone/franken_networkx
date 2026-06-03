# Alien Recommendation Card: Typed Native Sparse Export

## Symptom
Current-head profile showed simple `Graph` sparse exports with present `"weight"` attrs and `dtype=None` spent almost all time in Python adjacency-view iteration.

## Graveyard Primitive
- Source: `/data/projects/alien_cs_graveyard/alien_cs_graveyard.md`
- Matched entries: profile-first optimization loop, cache/locality data-structure guidance, and Swiss-table-style constant-factor reduction by replacing Python object/view probe paths with a contiguous native array handoff.

## Artifact-Coding Contract
- Runtime artifact: native default-order typed COO arrays `(rows, cols, data, needs_float_dtype)`.
- Proof artifact: `isomorphism_proof.md`.
- Golden artifact: `golden_sparse_digests.txt` plus `golden_sha256.txt`.
- Fallback policy: return `None` and use the existing Python fallback for bool/string/map weights, non-Graph inputs, explicit nodelists, non-CSR formats, multigraphs, and large integer weights outside exact f64 range.

## EV Matrix
| Candidate | Impact | Confidence | Effort | Score |
|---|---:|---:|---:|---:|
| Native typed default-order sparse arrays | 4 | 5 | 2 | 10.0 |

## Decision
Ship. The lever is narrow, behavior-isomorphic, and removes the profiled Python view path while preserving dtype inference.
