# br-r37-c1-tuxvu symmetric eigensolver Sturm-bisection probe

Status: rejected, evidence-only closeout.

Target:
- Profile-backed gap: raw safe-Rust `symmetric_eigvals_rust` on dense symmetric `n=200`.
- Baseline hyperfine: native mean 293.4ms, NumPy mean 267.2ms.
- Baseline in-process raw dense `n=200`: native median 0.004428236337844282s, NumPy median 0.0012919143385564287s.
- Baseline public weighted `laplacian_spectrum n=400`: FNX median 0.05274953902699053s, NX median 2.086006583995186s.

Lever tested:
- Replaced the tridiagonal QL solve for `128..=256` with a safe-Rust Sturm-sequence bisection primitive, leaving Householder tridiagonalization unchanged and preserving QL fallback outside the gate.

Behavior proof:
- Rust unit proof: `rch exec -- env CARGO_TARGET_DIR=/data/tmp/franken-networkx-algo-test-tuxvu cargo test -p fnx-algorithms tridiagonal_bisection_matches_ql_mid_size`
- Golden proof: `after_golden.json`
- Quantized native sha256: `87d7992502970de75d14e5c24ae33a702c010a18660e31e9f6eb0c299c994f64`
- Quantized NumPy sha256: `87d7992502970de75d14e5c24ae33a702c010a18660e31e9f6eb0c299c994f64`
- Max absolute delta: 7.105427357601002e-13
- Ordering: sorted ascending eigenvalues preserved.
- Floating point: no RNG; no public ordering/tie-break surface; values remain within the existing 10-decimal golden digest after narrowing the gate and returning the lower isolated bracket.

Benchmark result:
- After hyperfine native mean: 288.1ms, NumPy mean 268.8ms.
- After in-process raw dense `n=200` native median: 0.012952179337541262s.
- After raw dense `n=400` native median: 0.03128777403617278s. This is outside the bisection gate and is routing/noise evidence only.
- After public weighted `laplacian_spectrum n=400` FNX median: 0.034990110027138144s. This is outside the bisection gate and is routing/noise evidence only.

Decision:
- Rejected, Score 0.0.
- The golden proof was preserved, but the profile-backed `n=200` raw kernel regressed from 0.004428236337844282s to 0.012952179337541262s. The tridiagonal QL solve is not the right current subproblem for this size band.

Next routing:
- Do not repeat Sturm bisection for this lane.
- Attack the Householder tridiagonalization phase next: cache-blocked / row-parallel rank-2 update, preserving per-row arithmetic order and sorted eigenvalue output.
