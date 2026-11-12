# br-r37-c1-e92fj pass 13: current-community subvariants rejected

This note records the narrower current-community probes inside pass 13. The
pass-level keep is `pass14_ordered_working_keep.md`, which combines
current-community participation with ordered working-state materialization and
reduces raw failures to `0/18`.

## Candidate

Test the remaining `ws_300` residual called out by pass 12 by allowing the
node's current community to participate in the native Louvain one-level gain
evaluation.

Unchanged:

- MT19937 seed state and `randbelow(n)` bit-count behavior.
- Fisher-Yates node shuffle.
- Neighbor/community weight construction.
- Gain formula and strict `gain > best_gain` tie behavior.
- Coarsening, output conversion, and public Python routing.

## Baseline

- Golden: `louvain_pass13_before_golden.json`
- Raw/public summary: `public_failures=0/18`, `raw_failures=3/18`
- Golden SHA: `006f2fe09e992991eb0944f43be13f2cd5090114efa3a295edc23e10e9ddec11`
- Hyperfine raw `ws_300 seed=7 loops=20`: mean `0.26050765550s`, stddev `0.01788831437s`

Baseline raw failures:

```text
ws_300 seed=0
ws_300 seed=1
ws_300 seed=7
```

## Candidate Results

`after_current_gain`:

- Golden: `louvain_pass13_after_current_gain_golden.json`
- Raw/public summary: `public_failures=0/18`, `raw_failures=4/18`
- Golden SHA: `ed9388c279ff8f4e0bb57410436d2ca61c7bce7689526a506e8f6c5ea09faca7`
- Hyperfine captures for the focused row were `0.25823000490s` and `0.27946748020s`.

Raw failures:

```text
ws_150 seed=0
ws_300 seed=0
ws_300 seed=1
ws_300 seed=7
```

`after_current_loop`:

- Golden: `louvain_pass13_after_current_loop_golden.json`
- Raw/public summary: `public_failures=0/18`, `raw_failures=3/18`
- Golden SHA: `9321638694cffdc50dedceafff9e1fc50abf0e1813bcbbd71a43b337caadd97e`
- Hyperfine raw `ws_300 seed=7 loops=20`: mean `0.24965518836s`, stddev `0.00831349624s`

Raw failures:

```text
ws_150 seed=0
ws_300 seed=0
ws_300 seed=7
```

## Isomorphism Proof

- Public behavior preserved: all candidate captures kept `public_failures=0/18`.
- Internal raw behavior not preserved: `after_current_gain` introduced an extra
  raw mismatch, while `after_current_loop` fixed `ws_300 seed=1` but reintroduced
  the pass-12-fixed `ws_150 seed=0` mismatch.
- Ordering/tie-breaking/RNG: no intentional changes were made outside current
  community gain participation, so the changed raw artifacts isolate this lever.
- Golden outputs: `sha256sum -c` passed for baseline and both candidate golden
  files.

## Validation

- `rch exec -- cargo check -p fnx-algorithms --lib`: passed.
- `rch exec -- cargo test -p fnx-algorithms louvain --lib`: passed, 6 tests.
- `rch exec -- maturin develop --release --features pyo3/abi3-py310`: passed.
- `sha256sum -c louvain_pass13_before_golden.sha256`: passed.
- `sha256sum -c louvain_pass13_after_current_gain_golden.sha256`: passed.
- `sha256sum -c louvain_pass13_after_current_loop_golden.sha256`: passed.

## Verdict

Rejected and reverted.

The lever fails the behavior gate. One candidate worsens raw parity from
`3/18` to `4/18`; the other keeps `3/18` but changes which seed fails. The
best timing capture is not keepable because the golden raw contract changes.

Score: Impact `0` x Confidence `4` / Effort `2` = `0.0`.

Next target: see `pass14_ordered_working_keep.md`; current-community scanning
alone is not sufficient, but the ordered working-state primitive closes the raw
parity corpus.
