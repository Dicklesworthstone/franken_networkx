# br-r37-c1-fl36h — MultiGraph constructor unhashable-endpoint error parity

## Bug
fnx.MultiGraph([(unhashable, 3)]) leaked raw `TypeError: unhashable type`
from PyMultiGraph::__new__'s edge-list absorb loop (add_edge's eager
u.hash()? guard) instead of nx's
NetworkXError("Input is not a valid edge list"). The other three classes
absorb by id and translate in the Python __init__ hash-validation
backstop. 3 long-standing committed test failures
(test_constructor_edge_list_unhashable_endpoint_raises[MultiGraph-*]).

## Fix
TypeError -> NetworkXError("Input is not a valid edge list") translation
on every add_edge/add_node call inside the __new__ iterator-absorb branch
(mirrors nx to_networkx_graph wrapping from_edgelist failures). add_edge
OUTSIDE the constructor keeps raising TypeError (nx contract, probed).

## Proof
- trio now passes (file: 24 passed, 1 skipped).
- error-shape matrix: 4 classes x {list,set,dict} endpoints — exception
  type AND message equal to nx; add_edge TypeError contract preserved;
  valid 2/3-tuple constructions unchanged.
- full pytest: 21514 passed, 1 failed — ONLY the pre-existing
  coverage-matrix doc staleness remains.
