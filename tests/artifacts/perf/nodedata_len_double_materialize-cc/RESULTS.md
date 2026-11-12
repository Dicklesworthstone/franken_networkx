# NodeDataView.__len__ — return node count instead of materializing the list

## Lever
NodeDataView.__len__ did `len(self._materialize())`, building the entire
(node, data) tuple list just to count it. Because `list(view)` calls __len__
(size hint) THEN __iter__, every `list(G.nodes(data=...))` materialized the full
list TWICE. A NodeDataView is a bijection with the node set (one entry per node),
so its length is simply `len(self._view)` (O(1) native) — matching nx, whose
NodeDataView.__len__ is `len(self._nodes)`. Same view-wrapper double-materialize
anti-pattern fixed for EdgeDataView in br-r37-c1-ipm32.

## Correctness
list(G.nodes(data=...)) output and len() identical to nx across 40 cases
(Graph, node attrs, data {True,False,'w','missing',None}): 0 mismatches. golden
0a66f1379528e55c. Output is byte-identical to before (only __len__'s count path
changed — list() contents unaffected). 883 node-view + 1172 conformance/
conversion/utility/pickle tests pass.

## Benchmark (warm min, interleaved before/after)
| op                          | BEFORE    | AFTER     | self-speedup |
|-----------------------------|-----------|-----------|--------------|
| list(nodes(data=True)) n800 | 0.2703ms  | 0.1302ms  | 2.08x        |
| list(nodes(data='w')) n800  | 0.4888ms  | 0.2435ms  | 2.01x        |
| len(nodes(data=True)) n800  | 128.2us   | 0.78us    | 164x         |

~2x on a very hot view (nodes(data) is materialized by countless algorithms),
164x on len(). Residual (still ~10x slower than nx's 0.012ms for list()) is the
Rust NodeView __call__ tuple-materialization floor — fnx builds (node, dict)
tuples across PyO3 where nx iterates an existing {node: dict} mapping; closing it
needs a Python {node: dict} mirror (architectural, br-r37-c1-9hkgu).
