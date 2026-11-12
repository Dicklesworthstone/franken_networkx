# br-r37-c1-04z53.9121 Results

Target: repeated `DiGraph.predecessors(node)` / `DiGraph.successors(node)` row iteration on
`DiGraph(gnp_random_graph(n=1800, p=0.006, seed=15, directed=True))`.

Lever: replace the generic tuple-keyed private-aware neighbor wrapper for simple
`DiGraph` successor/predecessor rows with specialized per-kind live-row keydict
caches. The returned iterator is still a CPython dict-key iterator over the live
native row dictionary.

## Baseline

- Baseline source: detached parent worktree at `50e4116fa`, using the same freshly
  rebuilt `_fnx.abi3.so` as the candidate.
- Direct predecessor loop200: `0.227794003s`
- Direct successor loop200: `0.241883510s`
- RCH hyperfine loop400 predecessor: `1.008954490s +/- 0.043445392s`
- RCH hyperfine loop400 successor: `1.021767985s +/- 0.036142013s`
- cProfile predecessor total: `0.337s`; wrapper cumulative: `0.246s`

## After

- Direct predecessor loop200: `0.186939664s` (`1.22x`)
- Direct successor loop200: `0.188402073s` (`1.28x`)
- RCH hyperfine loop400 predecessor: `0.926229005s +/- 0.046486161s` (`1.09x`)
- RCH hyperfine loop400 successor: `0.947350314s +/- 0.046907442s` (`1.08x`)
- cProfile predecessor total: `0.267s`; wrapper cumulative: `0.190s`
- Score: Impact `1` x Confidence `4` / Effort `1` = `4.0`; keep.

## Isomorphism Proof

- Golden suite SHA unchanged: `839111081a858a447f2c14d220ba01d7db8e97fd6b561d6b6da4a997e2210517`.
- Predecessor output SHA unchanged and matched NetworkX:
  `8fb592ebe26699c141d47eba2a9e6c543dd985794e3b0708d6be5cb89770ebda`.
- Successor output SHA unchanged and matched NetworkX:
  `0e02f02397dbe4d298ed6a9750fc369e986684930fd419a386104db60321997a`.
- Ordering preserved: the native row dicts are populated in the same predecessor /
  successor row order as the previous generic cache and NetworkX reference rows.
- Mutation behavior preserved: both predecessor and successor iterators raise
  `RuntimeError: dictionary changed size during iteration` after row mutation,
  matching NetworkX.
- Missing and unhashable node behavior preserved: missing nodes raise
  `NetworkXError: The node missing is not in the digraph.`; unhashable list nodes
  raise `TypeError: unhashable type: 'list'`.
- Private-storage behavior preserved: if any private override is present, the
  wrapper falls back to the existing `succ` / `pred` mapping path.
- Tie-breaking, floating point, and RNG surfaces are unchanged: this path only
  selects row-key iterator plumbing and performs no algorithmic tie choice,
  arithmetic, or random draw.

## Validation

- `PYTHONPATH=python python3 -m py_compile python/franken_networkx/__init__.py tests/artifacts/perf/20260616T-digraph-neighbor-rowiter-coppercliff/digraph_neighbor_rowiter_harness.py`
- `PYTHONPATH=python python3 -m pytest tests/python/test_view_str_parity.py tests/python/test_graph_utilities.py tests/python/test_view_surface_mutation_parity.py tests/python/test_reverse_view_adj_parity.py tests/python/test_sort_neighbors_parity.py tests/python/test_dfs_predecessors_successors_dict_order_parity.py -k 'predecessor or successor or neighbor or DiGraph or edge' -q`
  -> `425 passed, 244 deselected`
- `cargo fmt --package fnx-python --check`
- `git diff --check`
- `rch exec -- maturin build --release --features pyo3/abi3-py310`
- `rch exec -- cargo check -p fnx-python --lib --features pyo3/abi3-py310`
- `rch exec -- cargo clippy -p fnx-python --lib --features pyo3/abi3-py310 -- -D warnings`
- UBS limitation: both `timeout 240s ubs --only=python --files=...` and
  `timeout 240s ubs --only=python --skip-python=20 --files=...` timed out with
  exit `124` during Python scanning; no UBS pass is claimed.
