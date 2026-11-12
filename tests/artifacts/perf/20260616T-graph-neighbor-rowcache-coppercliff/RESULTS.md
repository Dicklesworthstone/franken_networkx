# Graph.neighbors row-cache proof

Bead: `br-r37-c1-graph-neighbor-rowcache-coppercliff`

Target: `[list(G.neighbors(n)) for n in G.nodes()]` on
`Graph(gnp_random_graph(n=2400, p=0.0045, seed=23))`.

## Profile-backed baseline

- Current-head selector: FNX `0.001830138s/loop`, NetworkX `0.000866876s/loop`,
  ratio `2.11x`, output SHA `d3dda1a5981e4421e5f0766d650d4525f5e3adf69d95ab53ec1cc433e9c04331`.
- Baseline cProfile, 100 loops: `0.411s` total, `0.302s` cumulative in
  `_private_aware_neighbors`, with `720200` `dict.get` calls and `240200`
  `vars` calls.

## One lever

Specialized simple `Graph.neighbors` to a per-node live adjacency-row keydict
cache keyed by `(nodes_seq, edges_seq)`, analogous to the kept DiGraph
successor/predecessor cache. Directed and multigraph wrappers were not changed.

## Behavior proof

- Golden SHA unchanged:
  `2c3fa0649c4487ef239fe14c4076f5e1bced6d8ac599e415817ec097a5cb0b62`.
- Neighbor row output SHA unchanged and equal to NetworkX:
  `b99171852c6eeb1d713fec332be3c5adae9270e08127abedd6b2ac02014954f4`.
- Missing-node exception unchanged:
  `NetworkXError("The node missing is not in the graph.")`.
- Unhashable-node exception unchanged:
  `TypeError("unhashable type: 'list'")`.
- Active row iterator mutation behavior unchanged:
  `RuntimeError("dictionary changed size during iteration")`.
- Private `_adj` override fallback order unchanged: `[2, 1]`.
- No floating-point, RNG, or algorithmic tie-breaking surface is touched; the
  lever only changes simple-Graph neighbor row iterator dispatch.

## Benchmarks

RCH hyperfine, loop300:

| command | before mean | after mean | delta |
| --- | ---: | ---: | ---: |
| FNX | `1.0683961936s +/- 0.0322892432s` | `0.9538346428s +/- 0.0330755550s` | `1.12x` |
| NetworkX | `0.7723497409s +/- 0.0237666057s` | `0.7506473327s +/- 0.0277090307s` | comparator `1.03x` |

Focused upstream gap improved from `1.383x` to `1.271x`.

Direct timer, loop200:

| command | before s/loop | after s/loop | delta |
| --- | ---: | ---: | ---: |
| FNX | `0.001921234650` | `0.001638212820` | `1.17x` |
| NetworkX | `0.000758657925` | `0.000739754855` | comparator `1.03x` |

cProfile, 100 loops:

- Total: `0.411s -> 0.333s`.
- Neighbor wrapper cumulative: `0.302s -> 0.231s`.
- `dict.get` calls: `720200 -> 480200`.

Score: `Impact 4 x Confidence 5 / Effort 4 = 5.0`, keep.

## Validation

- `PYTHONPATH=python python3 -m py_compile python/franken_networkx/__init__.py .../graph_neighbor_rowcache_harness.py`
- Focused pytest: `106 passed, 577 deselected`.
- Broad adjacency-order pytest attempt hit unrelated exact-FP assertion in
  `test_delegated_rcm_consumer_matches_when_fairly_constructed`
  (`1.1102230246251565e-16 == 0.0`); no FP surface is touched by this lever.
- `cargo fmt --package fnx-python --check`
- `git diff --check`
- `rch exec -- cargo check -p fnx-python --lib --features pyo3/abi3-py310`
- `rch exec -- cargo clippy -p fnx-python --lib --features pyo3/abi3-py310 -- -D warnings`
- `ubs python/franken_networkx/__init__.py .../graph_neighbor_rowcache_harness.py .beads/issues.jsonl`
  timed out after 60s during Python scanning; no UBS pass claimed.
