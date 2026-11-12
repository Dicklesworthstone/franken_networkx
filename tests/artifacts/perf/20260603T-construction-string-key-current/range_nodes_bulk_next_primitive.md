# Next Primitive After Range Node Bulk

The range-node bulk path removes the profiled per-node Python wrapper and native `Graph.add_node` call loop for exact `Graph.add_nodes_from(range(...))`.

The shifted construction profile still has real gaps:

- `plain_edges_int`: FNX-vs-NetworkX ratio `2.025176159202857x`.
- `multigraph_int_keys`: FNX-vs-NetworkX ratio `4.6938179667281235x`.
- `multigraph_str_keys`: FNX-vs-NetworkX ratio `4.485727950204022x`.

The next construction pass should attack a different memory-layout primitive:

- intern integer node IDs into compact contiguous indices;
- store Python-side node/edge maps behind integer slots instead of repeated string lookups;
- preserve NetworkX observable insertion order and hash-equal key collapse;
- preserve int-vs-str distinction in Python-visible node objects;
- keep attr dict identity visible and lazily mutable;
- emit a golden digest over node type tokens, node order, edge order, keys, and attrs before keeping any source change.

Target ratio for the next primitive: reduce `multigraph_int_keys` from `4.69x` to under `2.0x` while preserving the digest `6041eefb1e549a77af5c18a4e08ab1dc24e9df42e2e9ef094e810d35bedf58dc`.
