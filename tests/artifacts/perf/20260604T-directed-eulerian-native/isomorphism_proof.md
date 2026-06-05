# Directed Eulerian Native Path Proof

Bead: `br-r37-c1-04z53.51`

## Change: simple DiGraph `eulerian_path` native reversed-Hierholzer traversal

- Ordering preserved: yes. The Rust helper builds the reversed directed adjacency by iterating `DiGraph.edges_ordered_borrowed()`, which matches the Python `G.edges()` insertion order used before NetworkX reverses the graph. The traversal consumes the first remaining outgoing reversed edge, matching NetworkX `_simplegraph_eulerian_circuit`.
- Tie-breaking unchanged: yes. Eulerian path start selection follows NetworkX's directed rules: explicit valid source is honored for Eulerian circuits; otherwise the reversed graph start is the node whose reversed out-degree exceeds in-degree. Circuit starts use graph node insertion order.
- Floating-point: N/A. The path is graph-structural and performs no numeric accumulation.
- RNG seeds: N/A. No random state is read or written.
- Errors and fallback: simple `DiGraph` without keys routes native. `MultiDiGraph` remains delegated so key and parallel-edge behavior stay NetworkX-owned. Missing source and no-path errors keep the existing NetworkX-compatible exception text.
- Golden outputs: `sha256sum -c artifact_sha256.txt` verifies the captured baseline, after, confirmation, benchmark, and validation artifacts. The behavioral digest stayed `55d6e89b71f957b470c6b51d788f3fd492661e6bd22d231f513fc0916bdcd45a` before and after.

## Baseline

- Profile-backed target: `tests/artifacts/perf/20260604T-directed-eulerian-native/baseline_cprofile.txt` and bead body showed `eulerian_path(DiGraph path, n=2000, repeats=1000)` spending the hot path in `python/franken_networkx/__init__.py:eulerian_path`, `_call_networkx_for_parity`, `_fnx_to_nx`, and NetworkX `eulerian_path`.
- Direct baseline: FNX mean `0.024045182805275546s`; NetworkX mean `0.015633572806837037s`; FNX/NX `1.5380478347700441`; digest matched.
- Baseline hyperfine, short process envelope: `0.3666099411s` mean for FNX with 3 inner repeats.

## After

- Direct after: FNX mean `0.004986111339045844s`; NetworkX mean `0.03477448924968485s`; FNX/NX `0.14338417174857662`; digest matched.
- Amplified confirmation: FNX mean `0.0014723998500267043s`; NetworkX mean `0.015463117838662584s`; FNX/NX `0.09522011442900917`; digest matched.
- Amplified process hyperfine, 200 inner repeats: FNX `0.8950888556200001s`; NetworkX `3.6085282206200007s`; FNX is `4.03x` faster.
- Profile shift: after cProfile over 1000 FNX calls reports `0.209s` wrapper time and `2.871s` in native `_fnx.eulerian_path`; `_call_networkx_for_parity` and `_fnx_to_nx` are no longer in the hot path.

## Score

- Impact: `5`
- Confidence: `5`
- Effort: `2`
- Score: `12.5`
- Verdict: PRODUCTIVE; keep.
