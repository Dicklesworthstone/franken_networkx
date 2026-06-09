# br-r37-c1-04z53.62 - k_components wheel certificate

## Target

No ready perf child was available after polling `br ready --json`, so this pass
opened a fresh child from a live profile-backed target. `fnx.k_components` still
delegated `wheel_graph(12)` to NetworkX parity, spending the run in
`networkx.algorithms.connectivity.kcomponents.k_components`,
`all_node_cuts`, `dag.antichains`, and `dag.transitive_closure`.

Baseline FNX profile:

- `3206070` calls in `0.915s`
- `k_components -> _call_networkx_for_parity -> nx.k_components`
- `all_node_cuts`: `45` calls, `0.902s` cumulative
- `dag.antichains`: `108083` calls, `0.381s` cumulative

After profile:

- `1146` calls in `0.001s`
- `k_components -> _wheel_k_components`
- no `_call_networkx_for_parity`, `all_node_cuts`, or DAG antichain frames

## One Lever

Add `_wheel_k_components`, a closed-form certificate for wheel graphs.

The fast path is only used for exact simple `Graph` objects with no self loops
and `flow_func is None`. The certificate requires:

- node count at least 5
- exact edge count `2 * (node_count - 1)`
- exactly one hub with degree `node_count - 1`
- every rim node has degree 3
- every rim node is adjacent to the hub
- rim-induced degree is exactly 2 for every rim node
- the rim-induced graph is connected, proving it is one cycle

Those constraints prove the graph is a hub plus one simple rim cycle. Non-wheel
graphs and custom-flow calls still delegate.

## Behavior Proof

Golden proof SHA is unchanged:

- baseline: `351a114ed29e184b79fab8334aa2c2373dd8aab7a39adfd305f0e86c98651896`
- after: `351a114ed29e184b79fab8334aa2c2373dd8aab7a39adfd305f0e86c98651896`

Direct golden result hashes:

| size | result sha256 | FNX/NX match |
| --- | --- | --- |
| 8 | `5a482ec83da0861e84eb03d66c13d374244b4bbabf914e0b94cbcd09f5fa59cc` | true |
| 10 | `20ebf9b7feb58e62d9458fb465be8a06d3d48d2201835273bb4551a82ef60730` | true |
| 12 | `0b7b69a03fcd53ab02f112b7ce7d384aa5fb3ec73890415579a9fa1ce853a818` | true |

Isomorphism checklist:

- Ordering: returned key order is `[3, 2, 1]`, matching NetworkX for wheels.
- Tie-breaking: each level contains one all-node component, so component order is
  uniquely determined.
- Floating point: not applicable; output is an integer node-set lattice.
- RNG: not applicable; graph builders are deterministic.
- Custom `flow_func`: fast path is disabled and the sentinel flow function is
  still observed like NetworkX.

## Benchmarks

RCH-wrapped hyperfine command family:

`harness_wheel.py time --which {fnx,nx} --size 12 --repeats 1`

| row | FNX mean | NX mean | FNX before/after | FNX vs NX |
| --- | ---: | ---: | ---: | ---: |
| baseline | `0.59772013388s` | `0.59371922248s` | `1.00x` | `0.99x` |
| after | `0.28202261340s` | `0.59738888080s` | `2.12x` | `2.12x` |

Direct in-process timing:

| size | baseline FNX | after FNX mean | after NX mean |
| --- | ---: | ---: | ---: |
| 8 | `0.01724956802s` | `0.00015665699s` | `0.01528478965s` |
| 10 | `0.05480842638s` | `0.00016823535s` | `0.05637138294s` |
| 12 | `0.31983345301s` | `0.00014673131s` | `0.31616855634s` |

Score: `Impact 4.0 x Confidence 4.5 / Effort 1.0 = 18.0`, keep.

## Validation

- `python -m py_compile python/franken_networkx/__init__.py tests/python/test_tree_kcomponents_assortativity_conformance.py tests/artifacts/perf/20260609T-k-components-wheel-boldfalcon-baseline/harness_wheel.py`
- `python -m pytest tests/python/test_tree_kcomponents_assortativity_conformance.py -q -k k_components` -> `50 passed, 49 deselected`
- `harness_wheel.py proof` -> unchanged SHA above
- `rch exec -- hyperfine ...` -> after artifact recorded
- `git diff --check`
- `ubs tests/python/test_tree_kcomponents_assortativity_conformance.py tests/artifacts/perf/20260609T-k-components-wheel-boldfalcon-baseline/harness_wheel.py` -> exit 0; only existing test-assert info
- `timeout 90s ubs python/franken_networkx/__init__.py` -> exit 124; no findings emitted before timeout and no leftover UBS children
- `rch exec -- cargo check -p fnx-python --all-targets --features pyo3/abi3-py310` -> exit 0; existing `fnx-generators` unused-result warnings remain
