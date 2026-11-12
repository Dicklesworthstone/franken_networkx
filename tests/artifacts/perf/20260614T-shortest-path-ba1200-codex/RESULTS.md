# br-r37-c1-04z53.81 Results

## Target

`shortest_path_pair_ba1200`: `shortest_path(barabasi_albert_graph(1200, 4, seed=11), 0, 900)`.

The profile-backed residual at claim time was FNX slower than NetworkX on the
unweighted point-to-point shortest path. The rejected prior wrapper-only lever
(`br-r37-c1-wkcpj`) was not repeated.

## Lever

One source lever: add an index-space sibling of the NetworkX-faithful
bidirectional BFS metadata kernel and route the Python raw
`bidirectional_shortest_path` binding through it.

The old string metadata path allocated a `Vec<&str>` per expanded row and used
owned `String` hash maps/frontiers. The accepted path keeps the same
frontier choice and meet-check order, but tracks visited/frontier/predecessor
state as node indices over the existing adjacency index rows.

## Isomorphism Proof

- Ordering: frontier selection remains `forward.len() <= reverse.len()` for
  forward expansion; current-level order and adjacency row order are unchanged.
- Tie-breaking: every scanned neighbor first records first discovery, then
  checks the opposite visited side, and returns immediately on the first meet,
  matching NetworkX `_bidirectional_pred_succ`.
- Reconstruction: predecessor chain to source is reversed, then successor chain
  is appended to target. The meet node still carries the returning frontier's
  `v` as display parent.
- Display objects: indexed output is resolved after the GIL is reacquired with
  the existing `py_row_key` / `py_pred_row_key` helpers; it does not collapse
  row-key objects to plain node-map objects.
- Floating point: not applicable; this is unweighted BFS.
- RNG: shortest path itself is deterministic; the BA graph fixture is generated
  with `seed=11` before timing.

Golden bundle SHA256 stayed unchanged:

```text
67e3d70817e4424b458f7d1540b4a97db6bd6b484fa5b5ddada30663339d513f
```

`baseline_golden.json` and `candidate_golden.json` are byte-identical.

## Benchmarks

Sequential direct median, 50k calls:

```text
FNX: 16.17321236000862 us/call -> 3.867565339896828 us/call
Speedup: 4.181755429745386x
Digest: b1f776746489abca9976b74a385449eeebb941eae20d2b1a21b3d2bf056e1513 unchanged
```

Hyperfine process mean, 50k calls:

```text
FNX: 1.0933775765s +/- 0.030595091886407917s -> 0.46156553424s +/- 0.025374179793361294s
Speedup: 2.368845798463533x
NetworkX candidate reference: 0.8356947915400001s +/- 0.026885106335966s
Candidate FNX vs NetworkX: FNX ran 1.81x faster
```

Profile shift, 20k calls:

```text
_fnx.bidirectional_shortest_path: 0.303s -> 0.058s
Total profiled call time: 0.414s -> 0.172s
```

Score:

```text
Impact 2.368845798463533 x Confidence 4 / Effort 1 = 9.475383193854132
Decision: keep
```

## Validation

```text
RCH_WORKER=hz1 CARGO_TARGET_DIR=/data/tmp/fnx_target_04z53_81_check rch exec -- cargo check -p fnx-python --lib
PYTHONHASHSEED=0 RCH_WORKER=hz1 rch exec -- .venv/bin/python -m pytest tests/python/test_bidi_efficiency_directed.py tests/python/test_traversal_tree_parity.py tests/python/test_shortest_path.py tests/python/test_multigraph_algorithms.py -q
RCH_WORKER=hz1 CARGO_TARGET_DIR=/data/tmp/fnx_target_04z53_81_test rch exec -- cargo test -p fnx-algorithms bidirectional_shortest_path --lib
sha256sum -c tests/artifacts/perf/20260614T-shortest-path-ba1200-codex/artifact_sha256.txt
```

Results:

```text
cargo check: passed, with pre-existing fnx-generators/fnx-python warnings
pytest: 200 passed
cargo test: 4 passed, 839 filtered out
artifact checksum check: passed
```

Known blockers outside this lever:

```text
cargo fmt --check -p fnx-algorithms -p fnx-python: blocked by pre-existing rustfmt drift across unrelated regions
cargo clippy -p fnx-algorithms -p fnx-python --lib --no-deps -- -D warnings: blocked by pre-existing fnx-python dead_code/collapsible_if/needless_borrow warning debt and fnx-generators unused-return warnings
ubs touched files: timed out in Rust scanner after Python scan finished; timeout exit 124 captured in ubs_touched.exit
```

## Re-profile

Post-change `profile_algorithms.py sweep` top rows:

```text
all_pairs_lca_dag450 ratio 0.9579388432327977, FNX 1.5400091740011703s, NX 1.6076278615073534s
descendants_dag450 ratio 0.9024371406842908, FNX 0.0001666349999140948s, NX 0.0001846499799285084s
ancestors_dag450 ratio 0.8929375425370399, FNX 0.00015834998339414597s, NX 0.00017733601271174848s
bfs_edges_ba1200 ratio 0.8151889567623022, FNX 0.00038024000241421163s, NX 0.00046644400572404265s
```
