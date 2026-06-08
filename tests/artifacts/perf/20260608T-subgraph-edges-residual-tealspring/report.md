# Nested Subgraph Edge Residual

Bead: `br-r37-c1-r3gjb`

Lever: collapse chains of default-edge, node-set subgraph views to the concrete parent for `_FilteredGraphView._edges`, then walk native plain-dict rows once. Simple graphs preserve source order and row order while gating by the intersected node set. Multigraphs replay each filter layer's `node_ok_shorter` set-vs-row branch before iterating key dictionaries, preserving parallel-edge ordering.

Proof:
- Baseline SHA: `c61e707f8b7509a8edd9eebab5ce6220e680308b1545bbe301ca72a3f95f28cf`
- After SHA: `c61e707f8b7509a8edd9eebab5ce6220e680308b1545bbe301ca72a3f95f28cf`
- Surface: nested Graph, DiGraph, MultiGraph, and MultiDiGraph edge views against NetworkX; covers edge-view class names, repr prefix, node order, iteration, call form, `data=True`, `data='weight'`, `data=None`, multigraph `keys=True`, parallel edges, self-loops, and attr payloads.

Hyperfine means:
- Nested Graph FNX: `2.12727231474s -> 0.45832958964s` (`4.64x`)
- Nested Graph NX: `0.55729787114s -> 0.55936811704s`
- Nested MultiGraph FNX: `7.84972275334s -> 0.51500121244s` (`15.24x`)
- Nested MultiGraph NX: `0.49792763274s -> 0.48622496564s`

Sample means:
- Nested Graph FNX: `1.883611066197045s -> 0.14108571901451797s` (`13.35x`)
- Nested MultiGraph FNX: `7.3881055833771825s -> 0.17091420716606082s` (`43.23x`)

Validation:
- `python3 -m py_compile python/franken_networkx/__init__.py .../subgraph_edges_residual.py`: pass
- Focused pytest: `5 passed`
- `tests/python/test_view_pickle_parity.py`: `262 passed`
- UBS harness: exit `0`
- UBS `python/franken_networkx/__init__.py`: exit `124` after timeout; stdout reports no critical/warning findings before timeout.
- `git diff --check`: pass

Score: Impact `5` * Confidence `5` / Effort `2` = `12.5`.
