# br-r37-c1-1n0tb Householder rank-2 update probe

Status: rejected, evidence-only closeout.

Target:
- Profile-backed gap: raw safe-Rust `symmetric_eigvals_rust` on dense symmetric `n=200`.
- Baseline in-process raw dense `n=200`: native median 0.004291954333893955s, NumPy median 0.0014350843460609515s.
- Baseline hyperfine: native mean 375.4ms, NumPy mean 296.6ms.

Lever tested:
- Split the adjusted Householder vector out of `e` into an `adjusted_scratch` buffer.
- Used that buffer to make lower-triangle rank-2 update rows independent, with a Rayon row-parallel update gate for active panels `>= 96`.

Behavior proof:
- Focused Rust proof: `rch exec -- env CARGO_TARGET_DIR=/data/tmp/franken-networkx-algo-test-householder cargo test -p fnx-algorithms symmetric_eigvals`
- Golden proof: `after_golden.json`
- Quantized native sha256: `87d7992502970de75d14e5c24ae33a702c010a18660e31e9f6eb0c299c994f64`
- Quantized NumPy sha256: `87d7992502970de75d14e5c24ae33a702c010a18660e31e9f6eb0c299c994f64`
- Max absolute delta: 1.7763568394002505e-13
- Ordering: sorted ascending eigenvalues preserved.
- Floating point: each matrix cell used the same algebraic operands as the scalar rank-2 update; no RNG; no public tie-break surface.

Benchmark result:
- After in-process raw dense `n=200` native median: 0.018400408676825464s.
- After hyperfine native mean: 642.6ms, NumPy mean 305.1ms.

Decision:
- Rejected, Score 0.0.
- The golden proof was preserved, but the profile-backed raw kernel regressed from 0.004291954333893955s to 0.018400408676825464s and process hyperfine regressed from 375.4ms to 642.6ms.
- Source reverted and clean release-perf extension reinstalled.

Next routing:
- Do not repeat per-row Rayon on this scalar Householder loop.
- Move to a fundamentally different primitive: blocked-panel Householder / `dsytrd`-class rank-2k update or tridiagonal divide-and-conquer/secular solve with a smaller proof surface.
