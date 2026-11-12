# br-r37-c1-85fvl alien recommendation card

## Selected primitive

Streaming argmax over a predecessor frontier.

## Contract

- Input: predecessor candidates in NetworkX-observable insertion order.
- Artifact: one streaming `(best_len, predecessor)` state per node.
- Runtime rule: update best only on strict greater-than.
- Exhaustion behavior: empty predecessor list still maps to `(0, v)`.

## EV score

- Impact: 2
- Confidence: 4
- Reuse: 3
- Effort: 1
- Adoption friction: 1
- EV: `24.0`

## Failure risks and guards

- Risk: tie-breaking drift on equal path lengths.
- Guard: strict `>` update preserves first maximum.
- Risk: hidden output drift on weighted default edges.
- Guard: focused parity test compares fast path, explicit-topo legacy path, and NetworkX on mixed present/missing weights.
