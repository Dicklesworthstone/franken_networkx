# Rejection Proof

Bead: `br-r37-c1-45n6t`

## Baseline

Profile command:

```text
RCH_ENV_ALLOWLIST=CARGO_TARGET_DIR rch exec -- cargo run -q -p fnx-algorithms --profile release-perf --features profile-pprof --bin perf_harness -- --pprof --pprof-top=20 --algo=harmonic --n=1600 --deg=5 --iters=3
```

Profile result:

```json
{"algo":"harmonic","n":1600,"m":4000,"avg_deg":5,"iters":3,"total_ms":396.1166,"per_iter_ms":132.0389,"checksum":1674332.847619}
```

Direct rch baseline:

```json
{"algo":"harmonic","n":1600,"m":4000,"avg_deg":5,"iters":5,"total_ms":306.3947,"per_iter_ms":61.2789,"checksum":2790554.746032}
```

Hyperfine baseline via rch:

```text
Time (mean +/- sigma): 230.2 ms +/- 3.3 ms
Range: 226.9 ms to 233.5 ms, 3 runs
```

The rch wrapper warned that hyperfine is not a compilation command, but the baseline command was still invoked through `rch exec`.

## Candidate

One lever tested: reuse BFS queue, distance vector, and generation-stamp vector across every source BFS in `harmonic_centrality_generic`.

Direct rch candidate result:

```json
{"algo":"harmonic","n":1600,"m":4000,"avg_deg":5,"iters":5,"total_ms":488.8929,"per_iter_ms":97.7786,"checksum":2790554.746032}
```

Delta: `61.2789 ms/iter -> 97.7786 ms/iter`, a 1.60x regression.

Score: `1.0`; below the required keep threshold of `2.0`.

## Isomorphism Proof

- Node iteration order remained `nodes_ordered()` order.
- Reverse-adjacency construction was unchanged.
- BFS queue semantics remained FIFO.
- Neighbor scan order remained exactly the stored reverse-adjacency vector order.
- Distance values assigned to reached nodes were identical; unreachable nodes were skipped equivalently by the old `unreached` sentinel and the candidate generation stamp.
- Harmonic accumulation still occurred only for reached popped nodes, in the same queue order, with the same `1.0 / (d as f64)` operation.
- There is no tie-break output other than node-ordered scalar scores.
- The algorithm uses no RNG; the harness graph seed remained fixed.

Golden output:

```text
before: 7a406fef51095b2fd8a838daea612411f09d5b6a9a0a97fdb407410dd0a8badb
after:  7a406fef51095b2fd8a838daea612411f09d5b6a9a0a97fdb407410dd0a8badb
```

`diff -u golden_before.txt golden_after.txt` produced no output.

## Revert Proof

Candidate source was reverted.

```text
git diff --quiet -- crates/fnx-algorithms/src/lib.rs
```

Exit status: `0`.

Verdict: rejected; no algorithm source change kept.
