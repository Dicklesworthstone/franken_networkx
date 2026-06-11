# br-r37-c1-fe1k0 — in-process Baswana-Sen spanner (1.6x faster than nx)

## Problem
Two underperforming spanner paths:
- `fnx.sparsifiers.spanner` ran nx's Baswana-Sen on an fnx graph *copy*
  (`residual_graph = G.copy()`, mutated with per-edge fnx-view overhead) then
  built an nx result and re-converted via `_from_nx_graph` — **2.4x slower than
  nx**.
- `fnx.spanner` (top-level) used the native `_raw_spanner` Rust kernel, which is
  itself **~1.5x slower than nx** (0.66x) — a real native-kernel underperformance.

## Lever
Reimplement Baswana-Sen **in-process** over plain Python dict-of-dict residual
adjacency keyed by the original node objects, building the fnx result graph
directly (no nx.Graph copy, no `_from_nx_graph`). Same algorithm, tight data
structures. `fnx.spanner` and `fnx.sparsifiers.spanner` both route to it
(`_spanner_inproc` in the clean `sparsifiers.py`); the top-level keeps nx's exact
validation contracts. The native `_raw_spanner` kernel is left in place (unused
by `spanner` now).

Spanner is randomized and its tie-breaks depend on node-object identity
(`id(u)` in nx), so parity is **structural** — a valid spanner with the
requested stretch (`assert_valid_spanner`), exactly as the function contracts —
not exact-edge.

## Result (vs genuine nx)
| n    | in-proc | genuine nx | speedup |
|------|---------|------------|---------|
| 400  | 8.14 ms | 13.66 ms   | 1.68x   |
| 800  | 17.73 ms| 29.54 ms   | 1.67x   |
| 1500 | 38.23 ms| 62.47 ms   | 1.63x   |

~2.3x vs the native `_raw_spanner` kernel; ~4x vs the old `sparsifiers.spanner`
submodule path. Consistent 1.6x across stretch 3-9.

## Proof
- Contracts: directed/multigraph → `NetworkXNotImplemented`; stretch<1 / empty →
  `ValueError` (matches nx); submodule routed.
- Validity: **285/285 valid spanners, 0 invalid** (`assert_valid_spanner`-style
  check over 30 seeds × 3 sizes × stretch {3,5,7} + 15 weighted).
- `tests/python -k spanner`: 27 passed, 0 failed (incl. the `assert_valid_spanner`
  approximation tests + the validation/guard-order regression locks).

## Note
The native `_raw_spanner` Rust kernel underperforming nx is itself a real
NO-GAPS target (optimize the Rust Baswana-Sen kernel to beat nx); this Python
in-process port is the immediate beat-nx win, consistent with the established
de-delegation pattern (boruvka / LPA / k_clique / large_clique_size).
