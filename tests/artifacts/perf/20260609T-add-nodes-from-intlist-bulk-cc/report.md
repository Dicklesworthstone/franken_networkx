# perf(add_nodes_from): native bulk int-list fast path (br-r37-c1-u2jod)

## Lever
`add_nodes_from(list_of_ints)` took a per-element Python loop calling `add_node`
across the PyO3 boundary once per node (hash() + bound dispatch + per-call int
extraction). A native bulk binding `_fast_add_int_nodes` EXISTED but was (a) only
wired for `range` inputs (the `range_stop` variant) and (b) itself eager —
allocating a `node_py_attrs` PyDict per node and using the recorded
`add_node_with_attrs` (decision-ledger tax).

Two changes (ONE lever — wire the bulk path):
1. Rewrote `_fast_add_int_nodes` to mirror `_fast_add_int_nodes_range_stop`:
   lazy attrs (drop the eager PyDict; materialize via `ensure_node_py_attrs` on
   access like the no-attr `add_node` branch) + a single unrecorded bulk inner
   insert (`extend_nodes_unrecorded`). Atomic validate-then-mutate; rejects
   non-exact-int and bool elements (`is_exact_instance_of::<PyInt>`) so the
   wrapper falls back (True/1 share a node but the general path keeps the `True`
   Py object for display).
2. Wired the wrapper (`_make_add_nodes_from`) to use it for `list`/`tuple` of
   plain ints (no attr, type(G) is Graph); TypeError/OverflowError -> general
   loop fallback. Restricted to list/tuple so generators are never half-consumed.

## Proof (byte-identical behavior)
14-scenario corpus (plain/dups/preexisting/tuple/bool_mix/negatives/attr_tuples/
nonint_fallback/grid_tuples/bigint_overflow/empty/global_attr/generator/set):
- OLD installed fnx: PARITY_OK, sha256 606fe8a9dbb8473f50cb7d7ca283852000cf5cfca49b3cfe9fc86ee85072691a
- NEW build:         PARITY_OK, sha256 606fe8a9dbb8473f50cb7d7ca283852000cf5cfca49b3cfe9fc86ee85072691a  (IDENTICAL)
- Both match genuine networkx on every scenario (0 mismatches).
- 494 pytest pass on the new build (177 construction/node-attr + 317
  generators/hypothesis/adj-order); fnx-python cargo check clean.

## Bench (warm min-of-N, add_nodes_from(list(range(50000))))
- before: fnx 92.44ms vs nx 15.82ms = 5.84x SLOWER
- after:  fnx 15.39ms vs nx 15.23ms = 1.01x  (PARITY)
- self-speedup 6.0x; vs-nx gap 5.84x slower -> parity (closed).
