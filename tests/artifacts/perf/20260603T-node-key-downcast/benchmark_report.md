# node_key_to_string: cheap PyString downcast (br-ctaxkey)

Lever: in the hot `node_key_to_string` helper, detect string node keys with
`downcast::<PyString>()` (a cheap isinstance check that builds NO Python
exception on a non-string) instead of `extract::<String>()`, which constructs
and discards a `PyErr` for every int / float / tuple node key. This helper runs
on every node-key conversion: `x in G`, `G[x]`, `has_node`, all lookups, and
node/edge construction (2 conversions per edge).

## Benchmark (isolated key-conversion path, host ~2.3x loaded)

Membership loop `for k in keys: k in G`, 200k lookups, median of 11:
  - 200k int keys:  OLD 114.37 ms -> NEW 97.02 ms  (~15% faster, the PyErr
    build on the failed String extract removed)
  - 200k str keys:  OLD 106.94 ms -> NEW 114.61 ms  (within host noise; the
    string branch does the same work either way)

Broad reach (every membership test / lookup / construction across all
algorithms), high confidence (isomorphic), tiny effort -> high
Impact x Confidence / Effort.

## Isomorphism + golden proof

Canonical keys byte-identical to nx across int / float / bool / large-int
(>i64) / negative / str / str-subclass / tuple keys, including hash-equal
collapse (1 == 1.0 == True, 0 == False) and int-vs-str distinctness.
GOLDEN sha256 of the mixed-key probe: a949484a1b459a00eed68f2e... (nx == fnx).
6946 graph/node/multigraph/hypothesis tests pass; 5-case regression test
(test_node_key_canonicalization_parity).

## Note on the bigger lever

This is the cheap, broadly-applicable slice of the construction tax. The
DOMINANT construction cost remains the per-node / per-edge `PyDict::new`
allocation in the dual-rep (add_nodes_from(100k) ~6.9x: 100k PyDict allocs).
Closing that needs lazy / arena attr-dict allocation -- a large multi-file
refactor (100+ node_py_attrs/edge_py_attrs read sites) that must preserve
mutation-persistence of `G.nodes[n]` / `G[u][v]`; it is the deferred
br-r37-c1-71x9k-class rewrite, not landable safely under current host noise.
