# Product / line_graph PLAIN kernels are DEAD (live path = *_fast) — NEGATIVE (cc, 2026-07-13)

Self-caught false-win record. Shipped a node-batch "2.86x" on the graph-product / line-graph kernels
(br-r37-c1-prodnodebatch, 7e709d9c1), then discovered the edited kernels are DEAD and REVERTED it
(98f66eef0). Documented so no peer re-mines these and so the `*_fast` bypass trap is on record.

## The trap: a binding calling `fnx_algorithms::X` does NOT prove X is live

`fnx_algorithms::{cartesian_product, tensor_product, cartesian_product_directed,
tensor_product_directed, line_graph, line_graph_directed}` ARE each called by a registered pyo3
binding (`_fnx.cartesian_product` @15817, `_fnx.line_graph` @15789, etc.). But those PLAIN bindings
are **never imported or called from any `.py`**. The live Python paths bypass them:

- `franken_networkx.cartesian_product/tensor_product/strong/lexicographic` (`__init__.py` ~23835)
  → `_native_graph_product` → `_fnx.cartesian_product_fast` / `tensor_product_fast` / … → the
  binding-layer builder **`graph_product_fast`** (algorithms.rs 15894), a DIFFERENT kernel.
- `operators.py` `cartesian_product` calls `_fnx.cartesian_product` where `_fnx = franken_networkx`
  (the PACKAGE) → resolves to the same `__init__.py` fast-path function, NOT the pyo3 binding.
- `franken_networkx.line_graph` (`__init__.py` 25924) → `_fnx.line_graph_fast` → **`line_graph_fast`**
  (algorithms.rs 16623), not `fnx_algorithms::line_graph`.

So the plain kernels are dead; the 2.86x A/B was real for the kernel in isolation but nothing reaches
it. **Reachability sub-rule (new): trace binding → the EXACT `fnx_algorithms::<fn>` it calls, and
check the `.py` doesn't route to a `*_fast` / `*_native` SIBLING that bypasses that binding.** A
registered binding that calls a kernel is necessary but NOT sufficient for the kernel to be live.

## The LIVE kernels are already fully batched (no lever)

`graph_product_fast` (15894): `inner.extend_nodes_unrecorded(canon…)` (16073, undirected) /
`extend_nodes_with_attrs_unrecorded` (15992, directed) + `extend_edges_unrecorded`. `line_graph_fast`
(16623): `extend_nodes_with_attrs_unrecorded` + `extend_edges_unrecorded`. Both batch nodes AND edges
already — the node-batch mirror-lag that afflicts the dead kernels does NOT exist in the live ones.

## Root cause of my miss + fix

I verified `_native_graph_product` was CALLED but assumed it used the `fnx_algorithms::cartesian_product`
kernel; it dispatches to `*_fast`/`graph_product_fast` instead. The A/B compiled and ran (real 2.86x)
but on a dead kernel, so compile+parity+A/B-pass did NOT catch the deadness — only tracing the Python
`.py` → binding → kernel chain does. Land-then-verify-reachability failed here; verify reachability
BEFORE the A/B next time.

## Net

Product / line-graph node-and-edge construction is fully optimized on every live path. Nothing to do
here. See [[pyo3_wrapper_can_itself_be_dead]] and the clique/coloring dead-kernel ledger for the
broader dead-kernel pattern; add the `*_fast`-sibling-bypass check to the reachability routine.
