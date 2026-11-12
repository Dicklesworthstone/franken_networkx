# br-r37-c1-3bdal native circular_ladder_graph constructor

## Target

After `br-r37-c1-7x2z3`, the ready perf bead was the generator residual
`br-r37-c1-3bdal`. A fresh baseline on `04af46b81` found:

- `circular_ladder_graph(2000)`: FNX direct median `5.098729ms`, NetworkX
  direct median `3.415471ms` (`1.49x` slower by direct timing).
- `random_regular_graph(8, 1500, seed=12345)`: FNX direct median
  `7.315729ms`, NetworkX direct median `6.462753ms` (`1.13x` slower).

The larger profile-backed target was circular ladder. Baseline cProfile over
120 FNX calls spent `0.665s` total: `0.663s` in `circular_ladder_graph`,
including `0.548s` in Python `add_edges_from` and `0.391s` in
`_try_add_edges_from_batch`.

## One lever

Use the generator-side native constructor for exact default
`circular_ladder_graph(n)` with integral `3 <= n <= MAX_N_GENERIC / 2`.
The Rust generator now emits edges in NetworkX-observable order:

1. top rail path,
2. bottom rail path,
3. rungs,
4. the two wrap-around closing edges.

Degenerate `n < 3`, custom `create_using`, and out-of-guardrail inputs remain
on the existing Python path. Random regular generation is unchanged.

An earlier algorithms-converter probe preserved proof but regressed and was
restored before this kept lever; the kept path avoids that converter entirely
and uses `report_to_pygraph`.

## Baseline and result

Direct benchmark, 25 samples after 5 warmups:

| Case | Before | After | Delta |
| --- | ---: | ---: | ---: |
| FNX median | 5.098729 ms | 2.440684 ms | 2.09x faster |
| FNX mean | 5.466343 ms | 2.556831 ms | 2.14x faster |
| NetworkX control median | 3.415471 ms | n/a | FNX now 1.40x faster than baseline NX |

RCH hyperfine, 12 runs, 80 calls/process:

| Command | Before mean | After mean | Delta |
| --- | ---: | ---: | ---: |
| FNX circular ladder | 0.694275 s | 0.458908 s | 1.51x faster |
| NetworkX control | 0.824417 s | 0.654748 s | control/envelope drift |

cProfile over 120 FNX calls dropped from `0.665s` to `0.273s` (`2.44x`).
The remaining hot frame is the native `_fnx.circular_ladder_graph_native`
constructor itself at `0.272s`.

## Isomorphism proof

Baseline and after proof files are byte-identical:

- Proof file SHA: `6fe7c16f307fb83743c582fe6da895e3ecc5ce9f0fb684145e9005138c25b3bb`
- Circular ladder digest: `e3c71666e1894596d6a3e8949cafe6bb4fb192776696d48dfe08b2218dc9dcba`
- Random regular digest: `cac80aef6f181434007d93ef151d69b54867433c4b54c30c76a3c24f3e55bf24`

Ordering is preserved by matching NetworkX insertion order exactly: top rail,
bottom rail, rungs, closing edges. Tie-breaking is not used. There is no
floating-point surface. Circular ladder has no RNG; the random-regular proof
case remains unchanged and keeps the same seeded digest.

## Gates

- `py_compile` for `python/franken_networkx/__init__.py` and the harness:
  passed.
- Focused pytest:
  `tests/python/test_classic_generators_adj_order_parity.py`,
  `tests/python/test_classic_generators.py`, and
  `tests/python/test_generator_structural_parity.py`: `236 passed`.
- `git diff --check`: passed before report generation.
- RCH `cargo check -p fnx-python --all-targets --features pyo3/abi3-py310`:
  passed on `vmi1227854` with pre-existing warnings.
- RCH `cargo test -p fnx-generators circular_ladder --lib`: local fallback
  due no admissible worker slots; crate-scoped, `3 passed`, same pre-existing
  warnings.
- `cargo fmt --check --package fnx-generators --package fnx-python` remains
  blocked by pre-existing formatting drift in untouched Rust files. A touched
  import-order diff from rustfmt was applied manually.

## Verdict

PRODUCTIVE / kept. Score `7.0` (`Impact 3.5 * Confidence 4.0 / Effort 2.0`).

Next target after push: reprofile the remaining `random_regular_graph` lane.
The next primitive should be Python-RNG-compatible native pairing or a
zero-copy edge batch from the Python RNG loop, not another circular-ladder
constructor pass.
