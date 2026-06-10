# BoldFalcon supplemental closeout

`br-r37-c1-t105o`

This supplement records the cod proof run that overlapped with `c64c58a22`.
That peer source commit already landed the sampled-row cache lever on `main`,
so this closeout intentionally does not modify `python/franken_networkx/__init__.py`.

Supplemental direct timing on BA n=2000, m=4, trials=1000, repeat=100:

- FNX median `10.0538ms -> 4.0128ms` (`2.51x`).
- Hyperfine FNX mean `1.020422s -> 0.744973s` (`1.37x`).
- Hyperfine FNX median `1.022109s -> 0.725304s` (`1.41x`).
- Value SHA unchanged: `03f0e797383cad483da2417075a9a77e9ca21246c3d1a2bec2c291c3d1992c9d`.

Supplemental proof SHA:

- Cod golden SHA unchanged: `98c10e70c8e765a24589f3d432967970dde53fd41ca7fe0abe3e2acdb4bbbe5d`.
- Source commit golden SHA from `c64c58a22`: `42cab3f8d9d37a071d57646e94382e237d7372aab501a4a19e529c8f6a1a800c`.

Validation from the cod proof run:

- `py_compile` passed.
- Focused approximation/cluster pytest: `120 passed`.
- `rch exec -- cargo check -p fnx-python --all-targets --features pyo3/abi3-py310` passed with pre-existing `fnx-generators` warnings.
- Clippy/fmt remained blocked by unrelated pre-existing Rust warnings/formatting drift.
- Bounded UBS timed out on the large Python wrapper without emitted findings.
