# Construction-tax survey (cc, 2026-06-13, HEAD-synced env)

After confirming the value-returning surface (undirected/directed/flow/IO/
conversion) is saturated at/above nx on a HEAD-synced env, the remaining
vs-nx perf frontier is **attributed graph construction**. Survey (8000 edges,
N=2000, min-of-8 warm; `survey.py` → `results.txt`):

    op                        fnx(ms)   nx(ms)  ratio
    Graph plain                  4.60     4.46  0.97x   ok
    Graph attributed             8.14     4.92  0.60x   <<<
    DiGraph plain                6.55     4.31  0.66x   <<<
    DiGraph attributed          11.08     5.70  0.51x   <<<
    MultiGraph plain            13.57    13.21  0.97x   ok
    MultiGraph attributed       52.56    14.93  0.28x   <<< worst
    MultiDiGraph plain          12.83    14.00  1.09x   ok
    MultiDiGraph attributed     54.46    22.30  0.41x   <<<
    add_nodes_from(20k)          6.56     5.30  0.81x
    copy                         0.98     9.76  9.97x   (native, 10x faster)

## Diagnosis

Attributed construction is 1.7-3.6x slower across ALL classes; plain
construction and copy are at parity-or-faster. Two distinct levers:

1. **MultiGraph/MultiDiGraph have NO batch fast-path** (br-r37-c1-trzrx).
   Simple Graph/DiGraph got `try_add_plain_edge_batch` + `try_add_attr_edge_batch`
   (lib.rs:1145/1339, digraph.rs:4251/4407); MultiGraph::add_edges_from
   (lib.rs:3359) still runs the per-edge `merged=PyDict::new()+add_edge()` loop
   (the same redundant merged-dict alloc PyGraph removed in br-r37-c1-aefbatch).
   Porting the batch path — handling parallel-edge key auto-increment,
   `edge_py_attrs[(u,v,key)]`, `edge_py_keys`, `adj_py_keys` cells — targets
   MultiGraph attributed 0.28x → ~parity (~3.6x). Multi-hour, key/mirror parity
   is fragile (needs an order-sensitive golden corpus).

2. **Simple-graph attributed residual 0.51-0.60x = dual storage.** Each edge
   stores BOTH an eager Rust `AttrMap` (via `py_dict_to_attr_map_with_mirror`,
   key-intern + `py_value_to_cgse` per value) AND the `Py<PyDict>` mirror; nx
   stores only the dict ref. Closing it needs **lazy AttrMap materialization**
   (store only the `Py<PyDict>` at construction; build the Rust `AttrMap` on
   first native-algo read). Bigger architectural swing; wide read-path blast
   radius. Target: attributed simple-graph 0.5-0.6x → ~parity.

These two levers gate metric_closure's residual, condensation (0.5x), and every
dense attributed graph build. The directive-aligned next swings; both are
multi-hour substrate work in the (peer-shared) fnx-python/fnx-classes Rust.
