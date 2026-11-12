# br-r37-c1-lni93: NodeView no-data iterator wrapper removal

## Profile target

Baseline profile for `list(G.nodes)` on a 20,000-node `Graph`, 50 loops:

- `0.356 s` total for 1,000,000 yielded nodes.
- `python/franken_networkx/__init__.py:45971(__iter__)`: 1,000,050 calls, `0.190 s` tottime.
- `builtins.len`: 1,000,100 calls, `0.089 s` tottime.

The Python mutation-detection wrapper was obsolete: Rust `NodeViewIterator` already carries
the O(1) `nodes_seq` and node-count fail-fast guard, including same-size key-change wording.

## One lever

Removed `_install_mutation_detection_on_node_views()` from the Python shim so public no-data
`NodeView.__iter__` uses the Rust iterator directly.

No Rust storage, ordering, attribute, floating-point, or RNG behavior changed.

## Isomorphism proof

Golden proof SHA:

- before: `f4f9df319125a62746af325ffaba898359ad2470b9a2edd6de0abb2ba84f08c4`
- after:  `f4f9df319125a62746af325ffaba898359ad2470b9a2edd6de0abb2ba84f08c4`

Covered surfaces:

- Node ordering and tie-breaking for hash-equal mixed keys: `0`, `0.0`, `True`, and `"0"`.
- Edge display order for the mixed-key graph.
- `nodes(data=True)` and `nodes(data="color", default=...)`.
- Mutation fail-fast wording for size change, same-size key change, `clear()`, and `add_edge()` creating a node.
- Existing-node `add_edge()` during node iteration does not raise.

Focused pytest:

`4 passed, 429 deselected` for graph node-iteration mutation parity tests in
`tests/python/test_review_mode_regression_lock.py`.

## Benchmark delta

Direct in-process medians, 20,000 nodes, 31 repeats:

| Case | Before | After | Speedup |
| --- | ---: | ---: | ---: |
| `list_graph_nodes` | `1.8206 ms` | `0.7008 ms` | `2.60x` |
| `consume_graph_nodes` | `2.0378 ms` | `1.0030 ms` | `2.03x` |

Hyperfine, same command shape, 20 runs, 40 loops per process:

- before mean: `370.1 ms +/- 20.6 ms`
- after mean: `316.9 ms +/- 17.1 ms`
- speedup including import/setup/build-graph overhead: `1.17x`

After profile:

- `0.046 s` total for the same 1,000,000 yielded nodes.
- Python wrapper frame removed from the hot profile.

## Score

Impact `4` x Confidence `5` / Effort `1` = `20.0`.

## Reprofile routing

This closes the obsolete Python-wrapper half of `br-r37-c1-lni93`. The next deeper primitive is
a persistent Python adjacency/successor/predecessor mirror so adjacency and neighbor iteration can
move to CPython dict-key iterators while Rust remains the algorithm store.
