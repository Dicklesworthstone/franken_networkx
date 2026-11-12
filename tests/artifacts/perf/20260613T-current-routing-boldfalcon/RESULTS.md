# br-r37-c1-wkcpj shortest_path wrapper coercion

## Target Selection

`br ready --json` still failed with SQLite `PRIMARY KEY constraint failed`.
Committed JSONL at `origin/main` had no open child perf beads, only the
umbrella `br-r37-c1-04z53`. Fresh current-head routing selected the only
digest-clean slower algorithm row:

- `shortest_path_pair_ba1200`: FNX median `20.328996us`, NetworkX median
  `16.820995us`, ratio `1.2085489605771975`, digest match.

## Lever

One Python wrapper lever only: after `shortest_path` has already validated and
coerced `G`, the unweighted source+target branch now calls
`_raw_bidirectional_shortest_path(G, source, target)` directly instead of
entering the public `bidirectional_shortest_path` wrapper and coercing again.

## Isomorphism Proof

Golden SHA unchanged:

- before: `c1d4e031e8490081f7ec88f794d3efa3ea827a1994dcd7d2a157d695ce59e79e`
- after:  `c1d4e031e8490081f7ec88f794d3efa3ea827a1994dcd7d2a157d695ce59e79e`

The proof compares seven NetworkX cases: BA pair, grid tie pair, directed tie
pair, `source == target`, no path, missing source, and missing target.

Ordering/tie-breaking is preserved because the raw bidirectional kernel is the
same kernel previously reached through the wrapper. RNG is not used by
`shortest_path`; the BA proof graph is deterministically constructed before the
call. Floating point is not involved in the unweighted branch.

## Original Benchmarks

Direct in-process median per call:

- baseline FNX: `16.371388849802316us`
- candidate FNX: `15.750704699894413us`
- speedup: `1.039406754283957x`
- NetworkX: `12.040756899659754us`
- output digest unchanged: `6532d1816ace4d72a30d5151173305897a0f0d5eef1f0c3e7951f3b46ef75f8d`

Hyperfine, 50k calls per process:

- baseline: `1.1157476339s +/- 0.0432541330s`
- candidate: `1.06124809452s +/- 0.0214448597s`
- speedup: `1.0513541929181507x`

Profile shift, 10k calls:

- baseline: `250001` calls, `0.205s`
- candidate: `170001` calls, `0.180s`
- removed path: `shortest_path -> wrapper -> bidirectional_shortest_path -> raw`

Score: Impact `1.0513541929181507` x Confidence `4` / Effort `1` =
`4.205416771672603`, keep.

## Rebased Verification

After rebasing the candidate onto `origin/main` parent `8b7fb51da`, the
proof was refreshed using fresh parent and candidate source worktrees with the
same rebuilt extension. Behavior stayed unchanged, but the timing no longer
qualified as a reliable real win.

- parent golden SHA:
  `c1d4e031e8490081f7ec88f794d3efa3ea827a1994dcd7d2a157d695ce59e79e`
- candidate golden SHA:
  `c1d4e031e8490081f7ec88f794d3efa3ea827a1994dcd7d2a157d695ce59e79e`
- output digest unchanged:
  `b1f776746489abca9976b74a385449eeebb941eae20d2b1a21b3d2bf056e1513`
- direct 100k median:
  `15.767742640018694us/call -> 15.85758330009412us/call`
- direct 100k mean:
  `15.85729626222423us/call -> 16.29409805781001us/call`
- paired 50k hyperfine:
  `1.130s +/- 0.063s -> 1.115s +/- 0.097s`, only `1.01 +/- 0.10x`
- profile calls:
  `250001 -> 170001`, but wall time did not improve reliably after rebase.

Rebased verdict: reject and do not keep the source hunk. This is a signal to
route away from wrapper micro-tuning and toward the next algorithmic primitive.

## Validation

- `rch exec -- cargo check -p fnx-python --lib`: passed; pre-existing
  `fnx-generators` unused-must-use warnings appeared.
- `python3 -m compileall -q python/franken_networkx ...`: passed via rch.
- `pytest tests/python/test_shortest_path_conformance_matrix.py
  tests/python/test_bidi_efficiency_directed.py
  tests/python/test_error_messages.py -q`: `70 passed`.
- `ubs` on the touched Python files stalled in its Python scanner after more
  than two minutes and was terminated by exact PID; no UBS finding was emitted.
