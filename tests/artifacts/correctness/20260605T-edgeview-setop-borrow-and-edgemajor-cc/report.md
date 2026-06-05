# EdgeView: fix set-op borrow panic (crash) + one-pass edge-major materialization

br-r37-c1-2zudj (perf, partial) + a pre-existing CRASH fix found alongside it.

## 1. CRASH FIX (correctness, headline): EdgeView set-op "Already borrowed" panic
`G.edges - sg.edges` (and `&`, `|`, `^`) panicked with
`pyo3_runtime.PanicException: Already borrowed: PyBorrowMutError` (views.rs
AtlasView.__getitem__) whenever the OTHER operand was a view over the SAME graph
(e.g. a subgraph view). `EdgeView.__sub__/__and__/__or__/__xor__` held
`self.graph.borrow(py)` across the iteration of `other`, and iterating a subgraph
view borrow_mut's the parent graph -> panic. This was failing the regression-lock
test test_s89yr_subgraph_filtered_edge_view_set_protocol on main HEAD.
Fix: collect self's (u,v) tuples via a helper that SCOPES the borrow to that call
(dropped before iterating `other`). All 4 set ops fixed.
Proof: setop_parity_proof.py — 28 cases (subgraph views x {-, &, |, ^} both
orders + plain-set) vs networkx, 0 mismatches; the failing test now passes
(2320 edge / 2472 view+subgraph pytest pass).

## 2. PERF: one-pass edge-major materialization for edges(data=True)
EdgeView.__iter__/__call__ AllData collected an owned `Vec<(String,String)>` of
endpoints (two String clones/edge) to release the `inner` borrow before the `&mut
materialize_edge_py_attrs` call. Field-split PyGraph (pub(crate) fields) so the
immutable inner/node_key_map borrow coexists with `&mut edge_py_attrs`: one pass,
reuse/materialize the LIVE attr-dict handle (d is G[u][v] preserved). The
sanctioned "edge-major assembly" technique (cf the peer's to_dict_of_dicts).
Proof: NEW==OLD byte-exact golden 9a14529d (incl identity); edges_nx_differential
80 cases (dir/undir, nbunch, data variants), 0 mismatches.
Perf (release A/B same build): edges(data=True) n=1500 1.70x->1.46x, n=4000
3.32x->2.73x (~1.3x self). Residual n>2000 cache cliff -> follow-up row-cache
(codex's dict_of_dicts_cache pattern), tracked in 2zudj.
