# Alien/No-Gaps Note

## Candidate Primitive

Payload-free native filtered copy for a hot induced-subgraph construction path.

## Why It Was Tried

The baseline profile showed the residual `ego_graph` copy tail dominated by Python edge materialization and generic batch edge insertion. The candidate attempted to harvest a bulk-transfer primitive: filter source edges in native code, avoid redundant `(u, v, data)` materialization, and populate empty edge attrs directly.

## Why It Was Rejected

The profile sample improved, but the higher-level wall-clock proof regressed:

- Direct rch sample mean regressed from `0.03052246606287857s` to `0.03164971126631523s`.
- Hyperfine mean regressed from `0.6168774760771429s` to `0.6682278137428571s`.

No source code from this primitive is kept.

## Next Candidate Guidance

Do not retry this exact native filtered-copy shape without a new profile showing a different bottleneck balance. The current evidence suggests the extra native method dispatch and filtering work can outweigh the removed Python materialization for this graph size.
