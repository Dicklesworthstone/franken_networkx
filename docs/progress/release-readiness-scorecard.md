# Release Readiness Scorecard

Target: FrankenNetworkX no-gaps performance gauntlet.

Scope of this update: cut-metric public wrappers from the recent code-first
pending backlog (`br-r37-c1-04z53.9155` and `br-r37-c1-04z53.9153`).

## 2026-06-19 Cut-Metric Gauntlet Slice

Environment:
- Commit under verification before this scorecard: `c04404c9a`.
- Reference: upstream `networkx 3.6.1` from `.venv`.
- Subject: editable local `franken_networkx` with release `_fnx.abi3.so`
  rebuilt by `maturin develop --release`.
- Bench command: `AGENT_NAME=CrimsonRiver CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b cargo bench -p fnx-python --bench networkx_head_to_head -- --sample-size 20 --warm-up-time 1 --measurement-time 2`.
- Criterion artifacts: `/data/projects/.rch-targets/franken_networkx-cod-b/criterion/networkx_head_to_head_cut_metrics/`.
- Focused conformance: `AGENT_NAME=CrimsonRiver .venv/bin/python -m pytest tests/python/test_graph_metrics_expansion.py tests/python/test_graph_metrics_conformance.py -q` passed with `197 passed in 0.85s`.
- Compile gate: `AGENT_NAME=CrimsonRiver CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b cargo check -p fnx-python --benches` passed.

| Bead | Workload | FNX mean | NetworkX mean | FNX speedup | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| `br-r37-c1-04z53.9155` | `edge_expansion`, BA2500 m=3, `|S|=1250` | 0.724 ms | 3.027 ms | 4.18x | Keep |
| `br-r37-c1-04z53.9155` | `edge_expansion`, WS2500 k=8 p=0.05, `|S|=625` | 0.367 ms | 1.775 ms | 4.84x | Keep |
| `br-r37-c1-04z53.9153` | `node_expansion`, BA2500 m=3, `|S|=1250` after revert | 1.080 ms | 0.481 ms | 0.445x | Rejected public fast path |
| `br-r37-c1-04z53.9153` | `node_expansion`, WS2500 k=8 p=0.05, `|S|=625` after revert | 0.488 ms | 0.281 ms | 0.577x | Rejected public fast path |

Pre-revert `node_expansion` evidence:
- BA2500/S1250 native public route: 0.713 ms vs NetworkX 0.527 ms, speedup 0.74x.
- WS2500/S625 native public route: 0.359 ms vs NetworkX 0.249 ms, speedup 0.69x.
- Revert rationale: the native public route improved over FNX fallback but did not beat
  the original NetworkX implementation, so it failed the campaign keep gate.

Score:
- Performance evidence: 32/40. One public fast path is a measured keep; one was measured
  and reverted instead of left pending.
- Conformance evidence: 25/25 for the focused cut-metric files. The run exposed and
  this commit fixes simple Graph/DiGraph `edge_boundary(S, T)` overlap ordering
  before recording the scorecard as green.
- Benchmark rigor: 16/20. Same interpreter, same graphs, setup outside timed loops,
  Criterion sample size 20; no flamegraph attribution in this narrow slice.
- Ledger hygiene: 20/20. Both keep and rejection are recorded in
  `docs/progress/perf-negative-results.md`.

Release readiness verdict for this slice: **conditional pass for `edge_expansion`;
no release claim for `node_expansion`**. Full project release readiness remains blocked
on the broader pending perf backlog and full conformance matrix.
