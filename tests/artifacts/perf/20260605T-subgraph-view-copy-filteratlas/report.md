# perf: SubgraphView.copy FilterAtlas node-set iteration

Bead: `br-r37-c1-rezuw`

## Baseline

Profile-backed target: `G.subgraph(keep).copy()` on a 2000-node parent with a
50-node induced set. The old fnx view scanned the full parent for visible nodes
and repeatedly called `_node_visible`.

- Baseline fnx min for 50 copies: `0.18044642399763688s`
- Baseline NetworkX min for 50 copies: `0.007578618009574711s`
- Baseline parity proof: `288` cases, `272` mismatches
- Baseline profile: about `705849` `_node_visible` calls on the cProfile run

## Lever

One lever only: carry NetworkX-style node-set metadata on induced filtered
views and mirror `FilterAtlas.__iter__`:

- if the filter has `.nodes` and `2 * len(nodes) < len(parent)`, iterate the
  node set directly and recheck parent membership;
- otherwise scan parent order and call the filter;
- keep arbitrary lambda filters on the parent-scan path.

This is an indexed filtered-view primitive: same view law, less parent scan.

## Proof

- Ordering preserved: changed to match NetworkX in the small-set branch;
  large-set and lambda-filter views keep parent order.
- Tie-breaking unchanged: edge iteration still uses parent neighbor/key order;
  only the observable outer node order follows NetworkX's own branch.
- Floating-point: N/A.
- RNG: N/A.
- Parent mutation visibility: allowed nodes are still checked against the
  parent graph at iteration time.
- Golden output: after proof `288` cases, `0` mismatches,
  SHA `d59bf72eb384ee5a2cfa0259051a1c6c5357b51dcd2e057d340b344cf1973d60`.

## Rebench

- After fnx min for 50 copies: `0.04373970296001062s` (`4.13x` faster than
  baseline fnx min).
- Focused hyperfine: current fnx ran `2.00x +/- 0.16` faster than the legacy
  scan behavior.
- After profile: `_node_visible` calls dropped from about `705849` to `39849`.

## Validation

- `rch exec -- env PYTHONPATH=... python3 parity_proof.py`: pass
- `rch exec -- env PYTHONPATH=... python3 -m pytest tests/python/test_subgraph_node_order_divergence.py tests/python/test_subgraph_view_no_copy_perf.py -q`: `54 passed`
- `rch exec -- env PYTHONPATH=... python3 -m pytest tests/python/test_view_pickle_parity.py tests/python/test_filtered_view_nodes_parity.py tests/python/test_adj_mapping_parity.py -q`: `356 passed`
- `rch exec -- env PYTHONPATH=... python3 -m py_compile python/franken_networkx/__init__.py tests/python/test_subgraph_node_order_divergence.py`: pass
- `sha256sum -c golden_sha256.txt`: pass
- `ubs tests/python/test_subgraph_node_order_divergence.py bench.py parity_proof.py`: pass, `0` warnings
- `ubs` including `python/franken_networkx/__init__.py`: timed out after `180s` on the known large-wrapper scanner path; no finding was emitted before timeout
