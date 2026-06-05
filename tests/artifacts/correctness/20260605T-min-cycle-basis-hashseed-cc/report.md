# br-r37-c1-cux5q — minimum_cycle_basis order parity at any PYTHONHASHSEED

## Bug
nx _min_cycle_basis derives the basis ORDER from CPython set iteration
(`chords = G.edges - tree_edges - {(v,u) ...}`), so nx's own output order
varies with PYTHONHASHSEED. fnx's unweighted fast path used the Rust
kernel's deterministic order — same cycles, different list order under
PYTHONHASHSEED=2 (two-triangles fixture; fnx [[b,c,a],[d,e,c]] vs nx
[[d,e,c],[b,c,a]]). Set-order-dependent output is the
parity-blocked-by-set-order class: unmatchable from Rust.

## Fix
Route unweighted minimum_cycle_basis through the existing
_minimum_cycle_basis_via_parity in-process nx-reference path (weighted
already did). Bench n=80/E~360: via_parity 7.34s vs nx 8.47s = 0.87x —
no upstream perf gap from the change (the abandoned Rust path was 0.02x
but order-divergent). _raw_minimum_cycle_basis retained for
order-insensitive internal callers.

## Proof
- seed matrix 0,1,2,3,7,42,99,1157: exact (order-sensitive) equality on
  the failing fixture + an 80-edge random graph.
- replaced the obsolete native-path pin test with
  test_minimum_cycle_basis_order_parity_under_adversarial_hash_seed
  (subprocess seeds 0/1/2/42).
- full pytest 21511 passed; failure set = pre-existing 4.
