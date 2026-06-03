# Isomorphism proof: rejected quotient raw edge insertion

## Scope

The tested candidate touched only the simple undirected default quotient path
where all of these were true:

- `edge_relation is None`
- `edge_data is None`
- `create_using is None`
- `G` is not directed
- `G` is not a multigraph
- default edge weights are integer-compatible

All other paths stayed on the previous implementation during the candidate.
After rejection, no source change remains.

## Ordering

The candidate did not alter the nested block-pair loops:

1. `i, block_u` from `enumerate(partition)`
2. `j` from `range(i + 1, len(partition))`
3. present `(i, j)` bucket keys only

The generated `edge_bunch` order was unchanged. Rejection restored the previous
public `H.add_edges_from(edge_bunch)` call.

## Attributes

For unweighted edges, tuples remained `(block_u, block_v)`. For weighted
default edges, tuples remained `(block_u, block_v, {weight: total})` with fresh
attribute dicts. Node data remained unchanged: `graph`, `nnodes`, `nedges`, and
`density` retained the same construction and insertion order.

## Floating Point And RNG

The candidate did not alter RNG use in the deterministic benchmark graph
generator. It did not alter density arithmetic, weight accumulation, or any
floating-point path.

## Golden

Baseline, candidate, confirm, restored, and NetworkX outputs all kept the same
digest for the benchmark case:

`34c9c354b368f5ae22d72d7f4635d9b9d263215bb31a2cf673e2e5203c2a5c52`

The manual restored parity helper produced digest:

`be4a4cda6ce2e3b45af2036a033b28ba01ab51dc9b294720543929290211ec48`
