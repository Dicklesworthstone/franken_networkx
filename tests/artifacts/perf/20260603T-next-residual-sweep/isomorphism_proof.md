# br-r37-c1-04z53.20 Isomorphism Proof

## Change
Route simple `Graph`, default-order CSR sparse exports with `dtype=None` and present string weights through a native typed COO helper.

## Baseline And Profile
- Baseline sample: `baseline_to_scipy_default_both.jsonl`
- Profile: `profile_to_scipy_default_fnx.txt`
- Hyperfine before: `hyperfine_to_scipy_default_before.json`
- Hyperfine after: `hyperfine_to_scipy_default_after.json`

## Behavior Invariants
- Ordering preserved: yes. The route is limited to `type(G) is Graph`, `nodelist is None`, and `format == "csr"`. Rows follow graph node insertion order; columns follow cached neighbor insertion order, matching the existing default-order native index helper and the Python fallback's adjacency iteration.
- Tie-breaking unchanged: yes. Sparse export has no algorithmic tie-breaker; duplicate canonicalization remains delegated to SciPy COO-to-CSR conversion.
- Floating-point preserved: yes for float weights. The helper reads synced edge attributes and returns the same `f64` values used by the existing dtype-pinned native weighted route. Integral float values still force float dtype because the helper tracks the original `Float` variant.
- Integer dtype preserved: yes for exactly representable `Int` values and missing weights. Large integers outside exact f64 range, bools, strings, and maps return `None` and keep the Python fallback.
- RNG unchanged: yes. The benchmark graph seed is fixed at `42`; runtime sparse export has no RNG.
- Error behavior unchanged: yes. The route runs after the existing empty/nodelist validation and falls back for unsupported value kinds.

## Golden Output
`golden_sparse_digests.txt` records baseline fnx, after fnx, and after NetworkX sparse digests. All are:

`12d41580d0336461201dbaa08fecc5250eab75162c958f5a91da80875db1ab37`

Verification:

```text
sha256sum -c tests/artifacts/perf/20260603T-next-residual-sweep/golden_sha256.txt
tests/artifacts/perf/20260603T-next-residual-sweep/golden_sparse_digests.txt: OK
```

## Performance
- Focused fnx sample mean: `0.3648216751986183s -> 0.028640794998500495s` (`12.7378x`)
- Hyperfine command mean: `2.5934042052399997s -> 0.9091851101600001s` (`2.8524x`)
- Profile after: Python adjacency-view iteration is gone; the top timed operation is the native helper plus SciPy construction.

## Score
Impact `4` x Confidence `5` / Effort `2` = `10.0`; keep.
