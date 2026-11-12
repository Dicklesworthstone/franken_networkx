# Benchmark Report: br-r37-c1-9kpev

## Target

Top-level `fnx.adjacency_data` on exact simple `Graph` / `DiGraph`.

Profile-backed hotspot: before the delegate, 30 directed calls took `1.782s`; most time was in Python adjacency view access (`_atlas`, `__getitem__`, and lambda wrapper frames).

## Lever

Delegate exact simple graph cases to `_fnx.adjacency_data_simple`, which returns the `nodes` and `adjacency` arrays in native storage order. The public wrapper still assembles the same outer payload and falls back for multigraphs, subclasses, and views.

## Baseline

- Graph direct mean: `0.0909907953615766s`, median `0.08824452199041843s`, SHA `51f3618da12dae4e6385a1276766f735a3a0bfff34581672c9cc7d7626ccefe9`.
- DiGraph direct mean: `0.03614856923813932s`, median `0.035373906983295456s`, SHA `3f96a2a9cb3040e532335e6a3af467f735284da8093ad3119fb3523fb5db17db`.
- Hyperfine command mean: `969.6 ms +/- 30.3 ms` for 20 top-level DiGraph calls.
- cProfile: `1.782s` for 30 directed calls.

## After

- Graph direct mean: `0.02073158783838153s`, median `0.019337395002366975s`, SHA `51f3618da12dae4e6385a1276766f735a3a0bfff34581672c9cc7d7626ccefe9`.
- DiGraph direct mean: `0.008549807079834864s`, median `0.008033888007048517s`, SHA `3f96a2a9cb3040e532335e6a3af467f735284da8093ad3119fb3523fb5db17db`.
- Hyperfine command mean: `512.9 ms +/- 26.4 ms` for 20 top-level DiGraph calls.
- cProfile: `0.270s` for 30 directed calls; time is now in `_fnx.adjacency_data_simple`.

## Delta

- Graph direct mean: `4.39x` faster.
- DiGraph direct mean: `4.23x` faster.
- Hyperfine process mean: `1.89x` faster.
- cProfile directed workload: `6.60x` faster.

## Score Gate

- Impact: 4
- Confidence: 5
- Effort: 1
- Score: `4 * 5 / 1 = 20.0`

Decision: keep and close.
