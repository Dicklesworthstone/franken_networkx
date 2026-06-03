# br-r37-c1-qp3v8 Benchmark Report

## Target

- Kernel: `fnx.node_connectivity(Graph)` global undirected path.
- Fixture: deterministic 400-node, degree-4 regular graph, seed `8675309`.
- Profile-backed hotspot: baseline cProfile spent `0.661s / 0.670s` in native `_fnx.node_connectivity`.
- Baseline vs upstream: FNX direct mean `0.6461622928036377s`; NetworkX direct mean `0.47069706360343844s`.

## Lever

Replace the global node-connectivity pair-local HashMap/String Edmonds-Karp residual with a safe-Rust indexed node-split residual and highest-label push-relabel cutoff kernel. The public local `node_connectivity(G, s, t)` and minimum-cut residual code remain on the existing path; this pass changes only the global value computation used by `fnx.node_connectivity(G)`.

## Baseline

- Direct FNX 5-sample mean: `0.6461622928036377s`; value `4`; digest `bbf21a609465999089e8d8f8c525e4235fd561c464d915517e0f6d65063ecb98`.
- Direct NetworkX 5-sample mean: `0.47069706360343844s`; value `4`; same digest.
- Hyperfine: `1.033s +/- 0.154s`, range `0.889s..1.311s`.
- cProfile: `0.670s`; native `_fnx.node_connectivity` `0.661s`.

## After

- Direct FNX 5-sample mean: `0.023341293196426704s`; value `4`; digest `bbf21a609465999089e8d8f8c525e4235fd561c464d915517e0f6d65063ecb98`.
- Direct NetworkX 5-sample mean: `0.46644879839150233s`; value `4`; same digest.
- Hyperfine: `303.7 ms +/- 20.7 ms`, range `264.6 ms..326.2 ms`.
- cProfile: `0.031s`; native `_fnx.node_connectivity` `0.023s`.

## Delta

- Direct FNX mean: `0.6461622928036377s -> 0.023341293196426704s` (`27.68x` faster).
- Direct FNX vs NetworkX: `1.37x` slower before; `19.98x` faster after on the same fixture.
- Hyperfine process mean: `1.033s -> 0.3037s` (`3.40x` faster).
- Native cProfile time: `0.661s -> 0.023s` (`28.74x` faster).

## Score Gate

- Impact: 5
- Confidence: 5
- Effort: 1
- Score: `5 * 5 / 1 = 25.0`

Decision: keep and commit.
