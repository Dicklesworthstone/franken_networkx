# br-r37-c1-04z53.9112 Baseline and Primitive Gate

## Target

Replace `adjacency_spectrum`'s `scipy.linalg.eigvals` dependency with a
100% safe-Rust native route without breaking NetworkX-observable dtype,
complex output, or raw solver order.

## Baseline

- Harness: `adjacency_spectrum_harness.py`.
- Golden corpus: path, cycle, BA, weighted BA, and directed-cycle graphs at
  sizes `4, 8, 32, 96`.
- Current FNX and genuine NetworkX raw-order SHA match:
  `ffefb05e26cb1bcd1a8bb2118888fa1668e0b2f00fbf04508dabab0f3ab52b4d`.
- Current sorted-value SHA match:
  `cdb8bb0687b7f775478dddd0330557ea751e9427baed7c1691251b8400a1a9b2`.
- Dtype parity holds: both return `complex128`.
- Max sorted absolute delta: `0.0`.

## Timing

- Weighted BA `n=160`: FNX median `0.006395257485564798s`, NetworkX median
  `0.006717377022141591s` after warm samples; no scoreable residual there.
- Weighted BA `n=400`: FNX mean `0.5264178226003423s`, median
  `0.5474783420213498s`; NetworkX mean `0.36766657599946484s`, median
  `0.34098891500616446s`.
- Hot FNX profile, weighted BA `n=400`, 3 loops: `1.261s / 1.265s` in
  `scipy.linalg.eigvals`; `adjacency_matrix` and sparse materialization total
  about `0.003s`.

## Rejected Before Source Edit

The obvious symmetric route, `symmetric_eigvals_rust(...).astype(complex128)`,
is not a valid one-lever change for this bead. It preserves the sorted value
set but not SciPy's raw solver order on every representative undirected case in
`baseline_scipy_order_probe.json`.

That matters because `br-r37-c1-aspec-cmplx` explicitly restored the public
contract to general `scipy.linalg.eigvals`: `complex128`, unsorted,
solver-defined order. Returning sorted symmetric eigenvalues would change an
observable sequence even when the values compare equal after sorting.

## Recommendation Card

Change: implement a safe-Rust real nonsymmetric dense eigenvalue primitive:
Householder reduction to upper Hessenberg form plus implicit double-shift QR
returning `Vec<(f64, f64)>`, exposed through PyO3 as `complex128`.

Hotspot evidence: hot profile is dominated by `scipy.linalg.eigvals`; matrix
construction is not the residual.

Mapped graveyard sections: `9.6 Communication-Avoiding Algorithms` for blocked
linear algebra and proof/tolerance contracts; numerical-linear-algebra family
34 for eigendecomposition verification.

EV score: Impact `5` x Confidence `2` / Effort `5` = `2.0`.

Fallback: keep the current SciPy path when the native QR path fails convergence,
when input is above the proven size gate, or when the raw-order proof corpus
does not match.

Isomorphism proof plan: raw-order SHA, sorted-value SHA, dtype `complex128`,
complex-conjugate-pair handling, directed-cycle complex corpus, and existing
spectral regression tests.

Baseline comparator: current `scipy.linalg.eigvals(adjacency_matrix(...).todense())`.

## Dense Array Route Rejection

Attempted route: replace `adjacency_matrix(...).todense()` with
`to_numpy_array(...)` before `scipy.linalg.eigvals`.

Parity artifact: `after_numpy_array_golden.json`.

- Raw-order SHA still matched NetworkX:
  `ffefb05e26cb1bcd1a8bb2118888fa1668e0b2f00fbf04508dabab0f3ab52b4d`.
- Dtype parity held: `complex128`.
- Max sorted absolute delta: `0.0`.

Timing rejected the route after the release-perf rebuild:

- Weighted BA `n=160`: baseline FNX median `0.006395257485564798s`; dense
  route median `0.35487756549264304s`.
- Weighted BA `n=400`: baseline FNX median `0.5474783420213498s`; dense
  route median `0.7956173790153116s`.

Decision: reverted from source. The route preserved behavior but failed the
Score gate.

## Native General QR Prototype

Prototype artifacts: `native_qr_proof.json`,
`native_qr_weighted_ba_n160.json`, `native_qr_weighted_ba_n400.json`, and
`prototype_general_qr_probe.json`.

Implemented a private safe-Rust primitive, exposed only as
`_fnx.real_general_eigvals_rust`, using:

- Householder reduction to upper Hessenberg form.
- Implicit double-shift QR eigenvalue extraction.
- `(real, imag)` output pairs for complex conjugates.

Numeric proof on the path, cycle, BA, weighted BA, and directed-cycle corpus:

- Sorted-value parity holds.
- Max sorted absolute delta: `1.4921397450962104e-13`.
- Native sorted SHA:
  `2f4de60072328aaf608cdb06058f5c904234e17c792ce27fca1206bd51f8e4c7`.
- SciPy sorted SHA:
  `cdb8bb0687b7f775478dddd0330557ea751e9427baed7c1691251b8400a1a9b2`.

Public route is still disabled because raw order does not match SciPy:

- Native raw SHA:
  `81217260da02fdbe8e13380ea68b4fba148223f161a3b4a6958837d9f5e2c308`.
- SciPy raw SHA:
  `ffefb05e26cb1bcd1a8bb2118888fa1668e0b2f00fbf04508dabab0f3ab52b4d`.

Harness timing through the native-QR harness path:

- Weighted BA `n=160`: native QR median `0.008985948981717229s`; current public
  FNX baseline median `0.006395257485564798s`; native is not a win.
- Weighted BA `n=400`: native QR median `0.1274556780117564s`; current public
  FNX baseline median `0.5474783420213498s`; native would be a win if raw-order
  parity were solved.

Direct eigensolver timing from `prototype_general_qr_probe.json`, excluding
graph/matrix construction:

- Weighted BA `n=160`: native QR median `0.008789891190826894s`; SciPy
  median `0.005868602590635419s`; native is not a win.
- Weighted BA `n=400`: native QR median `0.12616693999734707s`; SciPy median
  `0.46289462098502554s`; native is `3.668905824257598x` faster.

Decision: keep as a private prototype and proof artifact, but do not route
`adjacency_spectrum` until a raw SciPy-order proof passes. The next lever is a
Francis/LAPACK-order parity pass rather than another matrix-construction tweak.
