# br-r37-c1-pyun7: native current-flow betweenness route

## Target

- Bead: `br-r37-c1-pyun7`
- Hotspot: `current_flow_betweenness_centrality` / `edge_current_flow_betweenness_centrality`
- Profile-backed baseline: warmed cProfile on `watts_180` showed the FNX path dominated by `_flow_matrix_row`, `_FullInverseLaplacian.__init__`, and `numpy.linalg.inv`.
- Constraint: preserve NetworkX ordering, RCM relabeling, sorted-rank accumulation, node/edge output keys, and default full-solver semantics.

## Lever

Route the exact default simple-`Graph` full-solver path to a native safe-Rust kernel:

- Python still computes the existing NetworkX-compatible reverse Cuthill-McKee ordering.
- Rust builds the grounded reduced Laplacian in that order.
- Rust inverts it with the in-tree safe-Rust LU inverse.
- Rust computes per-edge flow rows as `weight * (Linv[u] - Linv[v])`.
- Rust applies NetworkX's sorted-rank node and edge accumulation formulas.

Fallbacks stay on the existing Python/NetworkX-compatible route for weighted graphs, custom solver arguments, non-default dtype, directed/multigraph cases, and unsupported graph classes.

## Baseline

Direct same-process FNX timings on `watts_120`, repeat 5:

- Node: median `0.90206258604303s`, mean `0.8432747543789446s`, result sha `5787cb9d9f731f3cfa66f71063cbb9358e5af4f7c32f4121547f5f421c9add8e`
- Edge: median `0.7263568409252912s`, mean `0.7980180060025305s`, result sha `6139eee3ab8d007f1715eca3b0f11ca34ecf5f1ae9bb87e83e2edcea6ff779f2`

RCH-wrapped hyperfine on `watts_180`:

- FNX node: mean `0.68408121266s`, median `0.63814030246s`
- FNX edge: mean `1.13087158066s`, median `1.12595964146s`
- NX node: mean `0.76137599746s`, median `0.77967246146s`
- NX edge: mean `1.07740387206s`, median `0.93905957346s`

Baseline proof:

- `all_close`: `true`
- `max_abs`: `1.1368683772161603e-13`
- `max_rel`: `2.065486211662824e-15`
- proof sha: `00910235fb97007e32551b5f28ca6de6f51b8df9bf7a53c1fcf09c184a2ef37b`

## After

Direct same-process FNX timings on `watts_120`, repeat 5:

- Node: median `0.004139999975450337s`, mean `0.004771870793774724s`, result sha `3f0a6dfb23f7c3f0a004cb9523a3be65c23ebc683e42fc7b9d0b5d28020be4a5`
- Edge: median `0.005525102955289185s`, mean `0.0058923890115693215s`, result sha `38885cf0776cbd15473fa91c7afc61495b469934b0bf5090b90b65d017da2185`

Direct self speedups:

- Node: `0.90206258604303s -> 0.004139999975450337s` = `217.89x`
- Edge: `0.7263568409252912s -> 0.005525102955289185s` = `131.47x`

RCH-wrapped hyperfine on `watts_180`:

- FNX node: mean `0.30712757434s`, median `0.29377538574s`
- FNX edge: mean `0.31499023714s`, median `0.31010230674s`
- NX node: mean `0.77051261554s`, median `0.75202984774s`
- NX edge: mean `0.75185217954s`, median `0.73944200974s`

RCH-wrapped process speedups:

- FNX node self: `0.68408121266s -> 0.30712757434s` = `2.23x`
- FNX edge self: `1.13087158066s -> 0.31499023714s` = `3.59x`
- After FNX node vs NX node: `2.51x`
- After FNX edge vs NX edge: `2.39x`

After proof:

- `all_close`: `true`
- `max_abs`: `1.4210854715202004e-13`
- `max_rel`: `2.753981615550432e-15`
- proof sha: `7ba0708a6b6442a641dea4ba6dfd47f5d83a9f05d66fe4f409ef8367be247a40`

The proof payload sha changes because the default path now uses the safe-Rust LU inverse instead of NumPy's inverse. Key ordering, node/edge output sets, and values remain within machine-scale drift and well inside the bead's `rel <= 1e-5` acceptance criterion.

## Validation

- `rch exec -- cargo check -p fnx-python --all-targets --features pyo3/abi3-py310`: passed on `vmi1227854`, with pre-existing `fnx-generators` unused-result warnings.
- `maturin develop --release --features pyo3/abi3-py310`: passed.
- Focused pytest: `18 passed, 220 deselected` for current-flow betweenness selectors.
- `rch exec -- cargo clippy -p fnx-algorithms --all-targets -- -D warnings`: passed.
- `rch exec -- cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings`: blocked by pre-existing `fnx-generators` `unused_must_use` errors.
- `git diff --check`: passed.
- `cargo fmt --check -p fnx-algorithms -p fnx-python`: blocked by pre-existing formatting drift outside the new hunk.
- `ubs --only=rust` on changed Rust files: completed; nonzero due existing broad repository heuristics and a false-positive "secret comparison" on graph group IDs. UBS Python scans timed out before findings.

## Verdict

Productive and kept. Score estimate: Impact `5` x Confidence `4` / Effort `1` = `20`.
