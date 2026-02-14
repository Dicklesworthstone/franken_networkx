# Risk Note

## Risk Surface
- parser/ingestion: malformed payloads for read/write edgelist and json graph.
- algorithmic denial vectors: adversarial graph shapes designed to trigger tail latency spikes.

## Failure Modes
- fail-closed triggers: unknown incompatible feature, contract-breaking malformed inputs.
- degraded-mode triggers: bounded hardened-mode recovery only when allowlisted and auditable.

## Mitigations
- controls: deterministic compatibility policy, strict/hardened split, packet-specific gate `parser adversarial gate`.
- tests: unit/property/differential/adversarial/e2e coverage linked through fixture IDs.

## Residual Risk
- unresolved risks: parser ambiguity; serialization round-trip drift.
- follow-up actions: expand fixture diversity and maintain drift gates as packet scope grows.
