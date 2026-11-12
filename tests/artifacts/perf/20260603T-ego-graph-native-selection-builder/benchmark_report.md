# br-r37-c1-0nkch Benchmark Report

## Target

- Profile-backed target: `ego_graph(Graph, 0, radius=2)` on BA(3000, 4, seed=42).
- Baseline residual: FNX direct mean `0.03204226841917261s`; NetworkX direct mean `0.022998212501988746s`.
- Baseline cProfile: 20 FNX calls spent `0.813s` cumulative in `ego_graph`; dominant visible costs were `Graph.add_edges_from` (`0.348s`), `EdgeDataView._materialize` (`0.150s`), and node-copy wrappers (`0.083s`).

## Lever

- Candidate: GraphBLAS / selection-vector style native radius-2 node mask plus insertion-order induced result builder.
- Scope: exact simple `Graph`, integer `radius == 2`, `center is True`, `undirected is False`, and `distance is None`.
- Fallback: all weighted, directed, multigraph, undirected-view, center-removal, subclass, non-int radius, and non-radius-2 cases stayed on the existing Python path.

## Baseline

- Direct FNX mean: `0.03204226841917261s`.
- Direct NetworkX mean: `0.022998212501988746s`.
- Hyperfine mean: `0.62744617802s` (`stddev 0.03576271082356162s`).
- Golden digest: `a66fe1d2d36fe1f69a5966fab6d739d8b5b34ed0aae622b17565fbba8ce603d6`.

## After

- Direct FNX mean: `0.03422747532371431s`.
- Hyperfine mean: `0.7039144615200001s` (`stddev 0.09410599058583338s`).
- Golden digest: `a66fe1d2d36fe1f69a5966fab6d739d8b5b34ed0aae622b17565fbba8ce603d6`.
- cProfile showed fewer Python calls and a lower profiled inner sample (`0.029106192949984688s`), but the non-profiled direct and hyperfine gates regressed.

## Restored

- Candidate source was removed.
- Restored direct FNX mean: `0.03105362699861871s`.
- Restored digest: `a66fe1d2d36fe1f69a5966fab6d739d8b5b34ed0aae622b17565fbba8ce603d6`.

## Score

- Impact: `0.0` because primary direct and hyperfine gates regressed.
- Confidence: `4.0` from matching direct, cProfile, hyperfine, restored sample, and focused tests.
- Effort: `2.0`.
- Score: `0.0`.
- Verdict: rejected; source restored and no optimization code kept.
