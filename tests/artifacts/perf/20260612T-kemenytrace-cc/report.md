# perf(kemeny_constant): deflated trace-of-inverse instead of full eigendecomposition

**Bead:** br-kemenytrace (no-gaps) · **Date:** 2026-06-12 · **Agent:** cc

## Gap

`kemeny_constant` was a verbatim copy of networkx: build the symmetric normalized
adjacency `H = D^-1/2 A D^-1/2`, then `np.sort(eigvalsh(H.todense()))` and sum
`1/(1-lambda_i)` over all but the top eigenvalue. fnx therefore sat at **parity with
nx** — both pay a full dense symmetric eigendecomposition O(9-22·n^3). At n=1500 that
is **1.23 SECONDS**. (Profiled on the dev tree via `PYTHONPATH=python`.)

## Lever (one) — alien-artifact: deflated resolvent trace

Kemeny's constant is `K = sum_{i: lambda_i != 1} 1/(1 - lambda_i)`. We need a SCALAR,
not the spectrum. For a connected graph the Perron eigenvalue `lambda = 1` is simple
with eigenvector `v0 = sqrt(deg)/||sqrt(deg)||` — exact even for weighted graphs and
self-loops, since `H v0 = D^-1/2 A 1 = v0`. Deflating it yields the SPD matrix

```
M = I - H + v0 v0^T
```

whose eigenvalues are `{1} ∪ {1 - lambda_i : lambda_i != 1}`, so
`trace(M^-1) = 1/1 + sum 1/(1-lambda_i) = 1 + K`, i.e. **K = trace(M^-1) - 1**.

`trace(M^-1)` via a Cholesky factorization + one batched solve is O(2/3..2·n^3) — an
order of magnitude fewer flops than the full eigendecomposition. A **size gate
(n < 256)** keeps small graphs on the original `eigvalsh` path: it is actually faster
there (the dense-solve fixed cost dominates) AND stays **bit-identical to networkx**
on every conformance fixture (all well under the gate).

Pure Python (numpy/scipy) — no native rebuild.

## Proof (behavior parity — absolute)

`verify_parity.py`: 16 shapes — complete, path, cycle, bipartite, petersen, karate,
self-loops, **weighted** (small + large), and large WS/BA up to n=1000, plus the gate
boundary n=256. Compares fnx vs nx relative error.

```
cases=16 worst_rel_err=2.08e-12 fails(>1e-9)=0
golden_sha256=0bd322fea42075600ee4bcd081eb58fbbdbf9770119d2b1e0a0ea77b2776747a
ALL PARITY OK
```

Worst rel error **2.08e-12** — six orders of magnitude inside the test tolerance
(`round(.,6)` / `tol=1e-6` / `pytest.approx`). 46 kemeny pytest pass.

## Benchmark (warm interleaved min-of-13; nx == old fnx, which was verbatim nx)

| graph  | n    | nx / old fnx | fnx after | self-speedup |
|--------|------|--------------|-----------|--------------|
| ws150  | 150  | 1.503 ms     | 1.436 ms  | 1.05x (no regression, eigvalsh path) |
| ws300  | 300  | 11.122 ms    | 6.672 ms  | **1.67x** |
| ba500  | 500  | 213.995 ms   | 26.616 ms | **8.04x** |
| ba800  | 800  | 70.656 ms    | 34.317 ms | **2.06x** |
| ws1000 | 1000 | 126.835 ms   | 51.076 ms | **2.48x** |
| ba1500 | 1500 | 1231.885 ms  | 105.437 ms| **11.68x** |

Headline: **1.67-11.7x faster for n≥300**, machine-exact, no small-graph regression.
Denser graphs (BA) win most — eigvalsh scales worse with spectral spread than the
Cholesky solve does.

## Follow-up

Same deflated-resolvent idea applies to any `sum f(1/(1-lambda))`-style spectral
scalar still on dense `eigvalsh` (audit `effective_graph_resistance`,
`estrada`-family if any remain on full spectra).
