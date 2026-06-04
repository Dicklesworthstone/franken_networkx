# br-r37-c1-p4mqd to_dict_of_dicts Isomorphism Proof

The code change removes only a redundant `Py<PyDict>` handle clone inside the
native `to_dict_of_dicts` builder. It does not change graph traversal, key
construction, value selection, or fallback routing.

## Ordering

- Outer node order still comes from `nodes_ordered()`.
- Undirected neighbor order still comes from `neighbors_iter(u)`.
- Directed successor order still comes from `successors_iter(u)`.
- No sorting, filtering, or duplicate handling changed.

## Value Identity

For existing edge-attribute dictionaries, the result now passes
`edge_dict.bind(py)` directly to `PyDict.set_item`. This stores the same Python
dict object that the prior `clone_ref(py).bind(py)` path stored, because
`set_item` retains the object reference.

For missing edge-attribute dictionaries, the code still creates a fresh empty
`PyDict` for that output value.

The golden check preserves:

- `fnx_matches_nx: true`
- `fnx_identity: true`
- digest `ca06db0d4f15b6bf38bdda3620ceccebb16c9e503abb39d15ac609872dae9b4f`
- record SHA `e5ca20d03e60a17015b200cf14d334af98ef21bdef44b1407a1916e66e156760`

## Tie-breaking

This conversion function exposes insertion order only. Since node and neighbor
iteration sources are unchanged, NetworkX-visible tie-breaking is unchanged.

## Floating Point and RNG

The target graph is attr-less and this function performs no floating-point
arithmetic and no random number generation. The benchmark graph uses a fixed
seed only to construct the fixture outside the API path.

## Fallbacks

The Python wrapper still delegates to the native builder only for
`nodelist is None`, `edge_data is None`, and exact simple `Graph` / `DiGraph`
types. Multigraphs, subclasses, filtered views, nodelist, and edge-data override
paths remain unchanged.

