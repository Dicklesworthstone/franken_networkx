# all_node_cuts / flow validation — concrete type fast-paths (br-r37-c1-31tby)

## Profile correction
The bead blamed `_has_networkx_private_storage`/`vars()` (64%). Profiling
all_node_cuts showed the real hotspot is FLOW-RESULT VALIDATION run on every
max_flow call: `_all_flow_caps_integral` + `_flow_has_infinite_capacity` scan the
whole flow graph's edges(data=True) doing `numbers.Integral`/`numbers.Real` ABC
isinstance checks (306k isinstance + 152k _abc_instancecheck per 2 runs).

## Levers (two small, same hotpath)
1. `_all_flow_caps_integral` / `_flow_has_infinite_capacity`: short-circuit the
   concrete int/float types before the ABC isinstance (ABC ~5x a concrete check).
   Provably equivalent (int/bool/float/numpy/None/Decimal all verified).
2. `_has_networkx_private_storage`: 4 `_private_override` calls (each its own
   `vars().get()`) -> ONE `vars()` snapshot + 4 short-circuit `in` checks
   (`k in vars(self)` == `get(k,MISSING) is not MISSING`). 318ns -> 120ns (2.6x).

## Correctness (isomorphism)
fnx-own flow output (value + value TYPE + flow dict with per-edge value types)
is BYTE-IDENTICAL before/after: sha 16a91682...e9ad unchanged across 60
maximum_flow cases x capacity types {int,float,inf,missing,negative}. maximum_flow
VALUE vs nx: 0 mismatches (flow-dict differences are pre-existing non-uniqueness,
unaffected). 1602 flow/cut/connectivity + 356 operator/conformance tests pass.

## Benchmark (warm min, interleaved) — ratio nx/fnx
| op                              | BEFORE          | AFTER           | self-speedup |
|---------------------------------|-----------------|-----------------|--------------|
| all_node_cuts BA(60,3)          | 29.38ms (0.58x) | 22.08ms (0.76x) | 1.33x        |
| all_node_cuts BA(100,4)         | 206.9ms (1.22x) | 180.4ms (1.40x) | 1.15x        |
| 4x maximum_flow_value           | 2.409ms (2.12x) | 1.714ms (2.89x) | 1.41x        |

Broad: every max_flow / min_cut benefits. maximum_flow_value 2.12x->2.89x faster
than nx; all_node_cuts 1.40x faster at n=100 (small-n residual is the native
max_flow + transitive_closure floor).
