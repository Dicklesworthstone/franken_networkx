# br-r37-c1-y0xps: MultiGraph difference int-index candidate

## Target

Profile-backed residual in exact `MultiGraph` / `MultiDiGraph`
`difference(G, H)` after the native result-construction path. Direct cProfile
showed nearly all FNX time inside `_native_difference`, so wrapper tuning was
not a valid lever.

## Baseline

- Direct `MultiGraph`: `0.011709846090525389s`, NetworkX `0.004371311981230974s` (`2.68x`)
- Direct `MultiDiGraph`: `0.010068948031403124s`, NetworkX `0.005031844018958509s` (`2.00x`)
- Hyperfine `MultiGraph`: FNX `0.8280s`, NetworkX `0.5938s` (`1.39x`)
- Hyperfine `MultiDiGraph`: FNX `0.7621s`, NetworkX `0.6845s` (`1.11x`)

## Candidate

Tried an integer-key indexed membership path inside native `_native_difference`
for `MultiGraph` and `MultiDiGraph`: build the H edge-membership set as
node-index plus integer display-key tuples, then probe G with the same indexed
form. The path bailed to the existing string-key implementation for non-integer
display keys.

## After

- Direct `MultiGraph`: `0.011709846090525389s -> 0.011050104047171772s` (`1.06x`)
- Direct `MultiDiGraph`: `0.010068948031403124s -> 0.009075945010408759s` (`1.11x`)
- Hyperfine `MultiGraph`: `0.8280s -> 0.7865s` (`1.05x`)
- Hyperfine `MultiDiGraph`: `0.7621s -> 0.7781s` (regressed)

## Proof

- Exact output order and content matched NetworkX before and after.
- `MultiGraph` SHA: `9e80720a651cd685a66a346bc2e6bfecdfc24c03679c68b67defbb30f5631d9c`
- `MultiDiGraph` SHA: `12c4dd6b3d7feabb4439a4dd2d5d36967aa1509b5e566947cf9879ce6e825021`
- Floating point: N/A.
- RNG: N/A.

## Verdict

Rejected. Score `0.0`: correctness held, but the win is too small and
`MultiDiGraph` hyperfine regressed. The next `y0xps` pass should use a broader
native primitive: native `symmetric_difference` / `intersection` set-op kernels
or a direct native `compose_all`/`union_all` fold for DiGraph/MultiGraph, not
more key-lookup micro-tuning inside `difference`.
