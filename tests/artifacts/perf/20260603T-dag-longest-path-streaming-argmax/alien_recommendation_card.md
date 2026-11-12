# Alien Primitive Card

- Skill pass: `/alien-graveyard` plus `/extreme-software-optimization`
- Borrowed primitive: allocation-free streaming reduction with stable tie policy.
- Local application: replace materialized candidate vectors in DAG DP with a streaming argmax accumulator.
- Safety boundary: only the exact-`DiGraph` native predecessor DP helper changes; generic fallback behavior is unchanged.
- Target ratio: remove the profiled candidate-list and `max(lambda)` tail after the predecessor bulk-snapshot pass.
- Observed result: direct path-only timing improved `0.0012655893466823425s -> 0.0011607977966195905s`, profile time improved `0.24168067899881862s -> 0.20199158298783004s`, and golden SHA stayed unchanged.

