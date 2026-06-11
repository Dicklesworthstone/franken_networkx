# convert.to_dict_of_dicts — route submodule to native fnx (~15x vs old path)

## Problem
`franken_networkx/convert.py` is a thin `from networkx.convert import *`
re-export, so `fnx.convert.to_dict_of_dicts` (and the
`from franken_networkx.convert import to_dict_of_dicts` import path) was nx's
pure-Python version. Run on an fnx graph it walks `G.adjacency()` / `G[u][v]`
views — **~15x slower** than the native `franken_networkx.to_dict_of_dicts`
(1.96 ms vs 0.13 ms at n=1000; 4.39 ms vs 0.28 ms at n=2000).

## Lever
Add a concrete `to_dict_of_dicts` to `convert.py` (clean / uncontested) routing
to the fnx top-level native implementation (same pattern as the shipped
operators routing). Byte-exact with nx incl. `nodelist` / `edge_data` args and
directed graphs. No Rust change; contested mid-refactor `__init__.py` untouched.

## Result
| n    | routed (fnx) | old submodule (raw nx) | genuine nx | vs old | vs nx |
|------|--------------|------------------------|------------|--------|-------|
| 1000 | 0.132 ms     | 1.959 ms               | 0.152 ms   | 14.9x  | 1.16x |
| 2000 | 0.276 ms     | 4.390 ms               | 0.322 ms   | 15.9x  | 1.17x |

## Proof
- `fnx.convert.to_dict_of_dicts` no longer nx's function (routed); import path
  routes too.
- Parity vs genuine nx: default+weighted 80/80 0 fails; `nodelist`, `edge_data`,
  digraph all 0 fails (`proof.json`).
- `tests/python -k "dict_of_dicts or convert"`: 59 passed, 0 failed.

## Notes (deep-target status)
- `to_dict_of_lists` / `from_dict_of_dicts` / `from_dict_of_lists` in convert
  are neutral or fnx-top-slower — not routed.
- `approximate_current_flow` (br-r37-c1-wz3sy) re-measured: NOT 12x — with a
  fixed seed it's parity-exact and only ~1.28x slower (conversion tax, numpy
  `_FullInverseLaplacian` same as nx). Downgraded to P3; the "12x" was a misread
  (vs fnx's *exact* kernel, a different non-sampled value). Deferred to when the
  mid-refactor `__init__.py` settles.
