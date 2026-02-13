# Contract Table

## Input Contract
| input | type | constraints |
|---|---|---|
| artifact payloads | mixed | must conform to schema v1 contract |

## Output Contract
| output | type | semantics |
|---|---|---|
| readiness status | enum | READY only when all mandatory artifacts + fields exist |

## Error Contract
| condition | mode | behavior |
|---|---|---|
| missing artifact | strict/hardened | packet marked NOT READY |
| missing required field | strict/hardened | packet marked NOT READY |

## Strict/Hardened Divergence
- strict: no repairs for missing mandatory schema fields
- hardened: still NOT READY for missing mandatory schema fields (diagnostics only)

## Determinism Commitments
- tie-break policy: lexical by packet_id for report ordering
- ordering policy: required artifact key order locked by schema
