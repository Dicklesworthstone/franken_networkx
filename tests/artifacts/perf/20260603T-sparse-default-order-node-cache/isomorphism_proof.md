# Isomorphism Proof: sparse default-order node cache

Bead: `br-r37-c1-04z53.33`

## Change Evaluated

Candidate cached `inner.nodes_ordered()` once inside `adjacency_default_order_arrays` and `adjacency_default_order_typed_arrays`, then indexed that insertion-ordered slice for row and column names instead of calling `inner.get_node_name(row)` and `inner.get_node_name(col)` in the loop.

## Behavioral Surface

- Ordering preserved: yes. Row iteration remained default graph insertion order, and neighbor iteration still used `inner.neighbors_indices(row)` without reordering.
- Tie-breaking unchanged: yes. Sparse export has no algorithmic tie-break; duplicate edge visitation order remained the graph adjacency order.
- Floating point unchanged: yes. Weight lookup and `f64` conversion logic were unchanged, and the same `default_weight` fallback path was used.
- RNG unchanged: yes. The benchmark graph seed remained `42`; the export path itself does not use RNG.
- Error/fallback behavior unchanged: yes. Non-Graph inputs, unsupported dtype values, and out-of-range integer weights retained the same fallback branches.

## Golden Output

Baseline FrankenNetworkX digest:

`12d41580d0336461201dbaa08fecc5250eab75162c958f5a91da80875db1ab37`

After-candidate FrankenNetworkX digest:

`12d41580d0336461201dbaa08fecc5250eab75162c958f5a91da80875db1ab37`

NetworkX oracle digest:

`12d41580d0336461201dbaa08fecc5250eab75162c958f5a91da80875db1ab37`

The candidate preserved observable sparse output, but it failed the performance gate and was restored.
