# br-r37-c1-fk6hk

Target: `Graph.subgraph(...).copy()` on sparse exact-int induced views with
empty node attrs.

Baseline target profile:
- `baseline_cprofile_fnx.txt`: `_FilteredGraphView.copy` 0.137s,
  `_copy_induced_simple_fast` 0.136s, `add_nodes_from` 0.033s,
  `_node_attrs_for_view_graph` 0.030s.

Rejected probe:
- Replacing `nodes = list(self)` with a list comprehension removed the
  length-hint call but regressed stable cProfile to 0.199s and hyperfine to
  680.7ms. The code change was reverted.

Kept lever:
- Route empty-attr exact-int `Graph` subgraph copies through the private
  Rust `_fast_add_int_nodes(Vec<i64>)` helper.
- Fallback remains unchanged for DiGraph, MultiGraph, MultiDiGraph,
  attributed nodes, non-int labels, bool labels, and oversized ints.

Same-environment hyperfine:
- `fnx-old`: 381.0ms +/- 29.6ms
- `fnx`: 356.5ms +/- 17.3ms
- `networkx`: 356.8ms +/- 41.6ms
- Full-command speedup: 1.07x over the pre-bulk path
- Target cProfile shift: `_copy_induced_simple_fast` 0.136s -> 0.065s

Behavior proof:
- Broad subgraph golden: 288 cases, 0 mismatches,
  sha256 `d59bf72eb384ee5a2cfa0259051a1c6c5357b51dcd2e057d340b344cf1973d60`
- Attr-state fast/fallback golden: 3 cases, 0 mismatches,
  sha256 `61a7613dd25126ba8860a96aa47030a74151ffb5c79b07078d1ac827e3312f68`
- Focused pytest: 68 passed
- `py_compile`, `cargo fmt -p fnx-python --check`,
  `cargo check -p fnx-python --all-targets`, and
  `cargo clippy -p fnx-python --all-targets -- -D warnings` passed via `rch`.
- UBS full touched set timed out after 180s while scanning the large Python
  wrapper; non-wrapper UBS exited 0 with no critical findings.
