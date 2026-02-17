# Contract Table

## Input Contract
| input | type | constraints |
|---|---|---|
| packet operations | structured args | must preserve NetworkX-observable contract for FNX-P2C-002 |
| compatibility mode | enum | strict and hardened behavior split with fail-closed handling |

## Output Contract
| output | type | semantics |
|---|---|---|
| algorithm/state result | graph data or query payload | deterministic tie-break and ordering guarantees |
| evidence artifacts | structured files | replayable and machine-auditable |

## Error Contract
| condition | mode | behavior |
|---|---|---|
| unknown incompatible feature | strict/hardened | fail-closed |
| malformed input affecting compatibility | strict | fail-closed |
| malformed input within allowlist budget | hardened | bounded defensive recovery + deterministic audit |

## Strict/Hardened Divergence
- strict: exact compatibility mode with zero behavior-repair heuristics.
- hardened: bounded, allowlisted defensive recovery while preserving outward API contract.

## Determinism Commitments
- tie-break policy: lexical canonical ordering for equal-priority outcomes.
- ordering policy: stable traversal and output ordering under identical inputs/seeds.
