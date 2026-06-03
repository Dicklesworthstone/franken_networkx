# Alien Primitive

Source: `/alien-graveyard` and `/alien-artifact-coding` pass for graph connectivity residual flow.

Primitive selected: replace repeated string-keyed Edmonds-Karp augmenting-path scans with an indexed preflow/push-relabel family:

- node-split residual represented as dense integer vertices and edge-index adjacency;
- highest-label active selection using a binary heap;
- gap relabeling for unreachable height bands;
- cutoff semantics for global connectivity, because only values below current `k` can change the result.

Proof obligation: preserve NetworkX-observable global node-connectivity integer values, candidate ordering, error/delegation prechecks, RNG independence, and deterministic golden SHA. The proof is in `isomorphism_proof.md`.
