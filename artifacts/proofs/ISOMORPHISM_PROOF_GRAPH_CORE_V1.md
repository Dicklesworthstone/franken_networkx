# Isomorphism Proof - Graph Core V1 Slice

## Change

Replace crate stubs with:
- deterministic graph mutation model,
- deterministic unweighted shortest path,
- fixture-driven conformance harness.

## Proof Checklist

- Ordering preserved:
  - yes, graph node/edge order is deterministic and insertion-stable in the implemented slice.
- Tie-breaking unchanged:
  - yes for this slice; BFS explores neighbors in insertion order.
- Floating-point:
  - N/A.
- RNG seeds:
  - N/A.
- Golden outputs:
  - fixture snapshots under `crates/fnx-conformance/fixtures/*.json` are stable and checked by tests.

## Compatibility Claim Scope

Applies only to first vertical slice:
- graph mutation,
- attribute merge,
- remove-node edge cleanup,
- unweighted shortest path.

Not a claim for full NetworkX API parity.
