# Validation Summary

Bead: `br-r37-c1-45n6t`

Status: rejected candidate, evidence retained, source reverted.

Profile-backed hotspot: `harmonic_centrality_generic<fnx_classes::Graph>`.

Baseline direct harness: `61.2789 ms/iter`, checksum `2790554.746032`.

Candidate direct harness: `97.7786 ms/iter`, checksum `2790554.746032`.

Golden SHA-256 before and after:

```text
7a406fef51095b2fd8a838daea612411f09d5b6a9a0a97fdb407410dd0a8badb
```

Source revert check:

```text
git diff --quiet -- crates/fnx-algorithms/src/lib.rs
```

Exit status: `0`.
