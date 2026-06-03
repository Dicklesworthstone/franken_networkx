# Alien Primitive Card

- Skill pass: `/extreme-software-optimization` rejection trigger with `/alien-graveyard` escalation.
- Rejected primitive: remove path reconstruction from `dag_longest_path_length` only.
- Reason rejected: the direct-length DP duplicated nearly all remaining work and saved only a small path-reconstruction/summing tail.
- Next primitive: fused topological-DP kernel that combines topological traversal, predecessor accumulation, and DP state in one native pass while preserving NetworkX stable predecessor-order ties.
- Target ratio: at least `1.5x` over current FNX length-only baseline and closing the current `1.32x` FNX-vs-NetworkX direct gap.

