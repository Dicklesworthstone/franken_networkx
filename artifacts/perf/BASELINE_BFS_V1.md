# Baseline - BFS V1

Command:

```bash
CARGO_TARGET_DIR=target-codex hyperfine --warmup 1 --runs 5 \
  'cargo run -q -p fnx-algorithms --example bfs_baseline'
```

Result:

- mean: `261.9 ms`
- stddev: `31.1 ms`
- min: `241.9 ms`
- max: `316.0 ms`

Notes:
- measures first implemented deterministic unweighted shortest-path slice.
- includes executable conformance witness output from example binary.
