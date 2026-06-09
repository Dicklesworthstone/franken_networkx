# br-r37-c1-04z53.61 - k_components ordered-prism certificate

## Target

Profile-backed residual after `br-r37-c1-kpsns`: `fnx.k_components`
delegated `circular_ladder_graph(10)` to NetworkX parity, spending the run in
`networkx.algorithms.connectivity.kcomponents.k_components`,
`all_node_cuts`, `dag.transitive_closure`, and `dag.antichains`.

Baseline FNX profile:

- `2537906` calls in `0.835s`
- `k_components -> _call_networkx_for_parity -> nx.k_components`
- `all_node_cuts`: `21` calls, `0.817s` cumulative

After profile:

- `619` calls in `<0.001s`
- `k_components -> _ordered_prism_k_components`
- no `_call_networkx_for_parity`, `all_node_cuts`, or DAG antichain frames

## One Lever

Add `_ordered_prism_k_components`, a closed-form certificate for ordered prism
graphs, including NetworkX's `circular_ladder_graph(n)` node order.

The fast path is only used for exact simple `Graph` objects with no self loops
and `flow_func is None`. The certificate requires:

- even node count at least 6
- exact edge count `3 * (node_count / 2)`
- every node has degree 3
- first half of iteration order forms a cycle
- second half of iteration order forms a cycle
- matching first/second-half rung edges exist

Those constraints plus the exact edge count prove there are no extra or missing
edges. Non-certificate graphs and custom-flow calls still delegate.

## Behavior Proof

Golden proof SHA is unchanged:

- baseline: `9030a61179ca1592a9dfa305dbfce32c428a185d38d78bdd85a4022e231235b4`
- after: `9030a61179ca1592a9dfa305dbfce32c428a185d38d78bdd85a4022e231235b4`

Direct golden result hashes for circular ladders:

| size | result sha256 | FNX/NX match |
| --- | --- | --- |
| 6 | `0b7b69a03fcd53ab02f112b7ce7d384aa5fb3ec73890415579a9fa1ce853a818` | true |
| 8 | `8cfc2c3249b1592195025af188baf87859cd09db210fd0b1f3612ff4f79993fb` | true |
| 10 | `1252bb817e244f4f6d13bde956635e2767f6d39671f2b4b85c55474267266eb6` | true |

Isomorphism checklist:

- Ordering: returned key order is `[3, 2, 1]`, matching NetworkX for prisms.
- Tie-breaking: each level contains one all-node component, so component order is
  uniquely determined.
- Floating point: not applicable; output is an integer node-set lattice.
- RNG: not applicable; graph builders are deterministic.
- Custom `flow_func`: fast path is disabled and the sentinel flow function is
  still observed like NetworkX.

## Benchmarks

RCH-wrapped hyperfine command family:

`harness_kpsns.py time --which {fnx,nx} --family circular_ladder --size 10 --repeats 1`

| row | FNX mean | NX mean | FNX before/after | FNX vs NX |
| --- | ---: | ---: | ---: | ---: |
| baseline | `0.56164894388s` | `0.56075231788s` | `1.00x` | `1.00x` |
| after | `0.27212188078s` | `0.54970224278s` | `2.06x` | `2.02x` |

Direct in-process timing:

| size | baseline FNX | after FNX mean | after NX mean |
| --- | ---: | ---: | ---: |
| 6 | `0.03830766701s` | `0.00008392786s` | `0.03376065412s` |
| 8 | `0.09101400210s` | `0.00007868628s` | `0.08996317682s` |
| 10 | `0.27570219408s` | `0.00008522456s` | `0.26365759571s` |

Score: `Impact 4.0 x Confidence 4.5 / Effort 1.0 = 18.0`, keep.

## Validation

- `python -m py_compile python/franken_networkx/__init__.py tests/python/test_tree_kcomponents_assortativity_conformance.py`
- `python -m pytest tests/python/test_tree_kcomponents_assortativity_conformance.py -q -k k_components` -> `45 passed, 49 deselected`
- `harness_kpsns.py proof` -> unchanged SHA above
- `rch exec -- hyperfine ...` -> after artifact recorded
- `git diff --check`
- `ubs tests/python/test_tree_kcomponents_assortativity_conformance.py` -> exit 0; only existing test-assert info
- `timeout 90s ubs python/franken_networkx/__init__.py` -> exit 124; no findings emitted before timeout and no leftover UBS children
- `rch exec -- cargo check -p fnx-python --all-targets --features pyo3/abi3-py310` -> exit 0; existing `fnx-generators` unused-result warnings remain
