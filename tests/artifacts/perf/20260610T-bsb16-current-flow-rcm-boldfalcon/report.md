# br-r37-c1-bsb16: native current-flow RCM start

## Target

- Bead: `br-r37-c1-bsb16`
- Hotspot: current-flow RCM ordering after `br-r37-c1-pyun7`
- Profile-backed baseline: after the solver and flow-row loop moved to Rust, warmed cProfile on `watts_180` showed `_reverse_cuthill_mckee_ordering` at about `0.006-0.007s` of a `0.012-0.013s` direct current-flow call. In the repeated RCM baseline profile, `_current_flow_pseudo_peripheral_node` accounted for `0.698s` of `0.974s` across 100 RCM calls.

## Lever

Move only the pseudo-peripheral start-node heuristic to safe Rust:

- Rust reproduces the BFS visit order, eccentricity growth loop, degree minimization, and first-min tie behavior over integer adjacency.
- Python still runs the connected Cuthill-McKee child ordering with `heuristic=start`.
- This deliberately preserves the existing Python `set(G[parent]) - visited` child tie behavior, which is CPython-set-order sensitive.

## Baseline

Direct same-process timings on `watts_180`:

- RCM repeat-100 median per call: `0.00228705198969692s`, mean `0.0023977355123497544s`, ordering sha `a8a2f2be38464506aec4c34d8f5fa0c05f108f6d23c03d441116bdf9f6dd60ca`
- Node repeat-20 median per call: `0.004748714971356094s`, mean `0.004840888932812959s`, result sha `dac0c13bb51c5d3801240be231ce7e4ca951e9e18dd57544d5e6fef52fbab53d`
- Edge repeat-20 median per call: `0.00468484393786639s`, mean `0.004989122797269374s`, result sha `2487bc9607acdde39ef93f367feea30e04d468de0e4a1971265075da2cea943d`

RCH-wrapped hyperfine on `watts_180`:

- RCM repeat-100: mean `0.49815637168s`, median `0.49268286388s`
- Node repeat-20: mean `0.34299247748s`, median `0.34069921988s`
- Edge repeat-20: mean `0.39631557088s`, median `0.40037890288s`

Baseline proof:

- Payload sha: `820fbbea0719ade1711e767173b6ea4b4cccdc62681cf309ed454311105107ad`
- Ordering sha for `watts_180`: `a8a2f2be38464506aec4c34d8f5fa0c05f108f6d23c03d441116bdf9f6dd60ca`
- Node sha for `watts_180`: `dac0c13bb51c5d3801240be231ce7e4ca951e9e18dd57544d5e6fef52fbab53d`
- Edge sha for `watts_180`: `2487bc9607acdde39ef93f367feea30e04d468de0e4a1971265075da2cea943d`

## After

Direct same-process timings on `watts_180`:

- Native-start RCM repeat-100 median per call: `0.0008733740542083979s`, mean `0.0008424924092832953s`, ordering sha `a8a2f2be38464506aec4c34d8f5fa0c05f108f6d23c03d441116bdf9f6dd60ca`
- Node repeat-20 median per call: `0.0031093789730221033s`, mean `0.0029155897093005477s`, result sha `dac0c13bb51c5d3801240be231ce7e4ca951e9e18dd57544d5e6fef52fbab53d`
- Edge repeat-20 median per call: `0.0022970010759308934s`, mean `0.002397159446263686s`, result sha `2487bc9607acdde39ef93f367feea30e04d468de0e4a1971265075da2cea943d`

Direct self speedups:

- RCM: `0.00228705198969692s -> 0.0008733740542083979s` = `2.62x`
- Node: `0.004748714971356094s -> 0.0031093789730221033s` = `1.53x`
- Edge: `0.00468484393786639s -> 0.0022970010759308934s` = `2.04x`

RCH-wrapped hyperfine on `watts_180`:

- Native-start RCM repeat-100: mean `0.33702697402s`, median `0.32286361002s`
- Node repeat-20: mean `0.31483228182s`, median `0.30723703202s`
- Edge repeat-20: mean `0.31528350002s`, median `0.31251098102s`

RCH-wrapped process speedups:

- RCM repeat-100: `0.49815637168s -> 0.33702697402s` = `1.48x`
- Node repeat-20: `0.34299247748s -> 0.31483228182s` = `1.09x`
- Edge repeat-20: `0.39631557088s -> 0.31528350002s` = `1.26x`

After proof:

- Native start matched Python start for all proof cases.
- Native-start RCM ordering matched Python RCM ordering for all proof cases.
- `watts_180` ordering sha unchanged: `a8a2f2be38464506aec4c34d8f5fa0c05f108f6d23c03d441116bdf9f6dd60ca`
- `watts_180` node sha unchanged: `dac0c13bb51c5d3801240be231ce7e4ca951e9e18dd57544d5e6fef52fbab53d`
- `watts_180` edge sha unchanged: `2487bc9607acdde39ef93f367feea30e04d468de0e4a1971265075da2cea943d`

## Validation

- `rch exec -- cargo check -p fnx-python --all-targets --features pyo3/abi3-py310`: passed with pre-existing `fnx-generators` warnings.
- `maturin develop --release --features pyo3/abi3-py310`: passed.
- Focused native RCM/current-flow tests: `3 passed, 47 deselected`.
- Focused current-flow selector suite: `18 passed, 221 deselected`.
- `rch exec -- cargo clippy -p fnx-algorithms --all-targets -- -D warnings`: passed.
- `rch exec -- cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings`: blocked by pre-existing `fnx-generators` `unused_must_use` errors.
- `cargo fmt --check -p fnx-algorithms -p fnx-python`: blocked by pre-existing formatting drift outside the new helper region.
- `git diff --check`: passed.
- Harness `py_compile`: passed.
- Focused Python `ubs` on the changed test/harness/report completed nonzero on pre-existing assert heuristics in `test_centrality_extensions_parity.py`; the new RCM test uses explicit `raise AssertionError`.
- Rust-only `ubs` on the touched Rust files completed nonzero on existing broad-file findings, including the known false-positive graph group-id "secret comparison".

## Verdict

Productive and kept. Score estimate: Impact `3` x Confidence `4` / Effort `2` = `6`.
