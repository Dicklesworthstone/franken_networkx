# br-r37-c1-rm8nz - k_components ordered two-clique bridge certificate

## Target

Profile-backed follow-up after the ordered-prism and 2-degenerate
`k_components` certificates. The `jfsyo` residual artifact showed
`paired_clique_barbell/8` and `near_barbell_bypass/8` still reaching
NetworkX's Moody-White / Kanevsky fallback:

- `k_components -> _call_networkx_for_parity -> nx.k_components`
- `all_node_cuts`
- DAG `transitive_closure` / `antichains`
- Edmonds-Karp flow was present but not dominant.

## One Lever

Add `_ordered_two_clique_bridge_k_components`, a guarded closed-form
certificate for exact simple `Graph` inputs whose iteration-ordered core is two
equal complete cliques connected by either:

- two direct bridge edges with distinct endpoints on both cliques, or
- one direct bridge plus one degree-2 bypass node whose endpoints are distinct
  from the direct bridge endpoints.

The accepted graph must be biconnected and self-loop free. Custom `flow_func`
calls and every failed certificate still delegate to NetworkX.

## Behavior Proof

Golden proof SHA is unchanged:

- baseline: `87b4f1437d40c95729484fd6a78c7b6d35a39a3a0baddc4c62d956f77edf749d`
- after: `87b4f1437d40c95729484fd6a78c7b6d35a39a3a0baddc4c62d956f77edf749d`

Target result SHAs stayed unchanged:

| Case | SHA256 |
| --- | --- |
| `paired_clique_barbell/8` | `a5701ad4e863ba769bc7ce0890bb71fb3f4cd1035a1d1e52ea4aaff8e9c96caf` |
| `near_barbell_bypass/8` | `7e95f6875d1682b0e16b81a858df6dec2ff66d0d8b2238dbdeb4e2e608b8a95d` |

Isomorphism checklist:

- Ordering: descending key order is preserved; clique component order follows
  graph iteration order and matches NetworkX on proof cases.
- Tie-breaking: accepted cases have two ordered high-k clique components and
  one whole-graph component at k=2 and k=1.
- Floating point: not applicable; output is an integer node-set lattice.
- RNG: not applicable; graph builders are deterministic.
- Custom `flow_func`: fast path is disabled and the sentinel flow exception is
  still observed like NetworkX.

## Benchmarks

Direct in-process timings:

| Case | Baseline FNX mean | After FNX mean | Speedup |
| --- | ---: | ---: | ---: |
| `paired_clique_barbell/8` | `15.878 ms` | `0.208 ms` | `76.3x` |
| `near_barbell_bypass/8` | `24.840 ms` | `0.205 ms` | `121.0x` |

RCH-wrapped hyperfine, 5 calls per command:

| Case | Baseline mean | After mean | Speedup |
| --- | ---: | ---: | ---: |
| `paired_clique_barbell/8` | `450.4 ms` | `312.1 ms` | `1.44x` |
| `near_barbell_bypass/8` | `483.2 ms` | `313.5 ms` | `1.54x` |

After profiles:

- `paired_clique_barbell/8`: `816,493` calls / `0.336s` for 5 baseline calls
  became `6,260` calls / `0.002s`.
- `near_barbell_bypass/8`: `1,274,164` calls / `0.437s` for 5 baseline calls
  became `6,465` calls / `0.002s`.
- `_call_networkx_for_parity`, `all_node_cuts`, and DAG transitive-closure
  frames are gone for accepted cases.

Score: `Impact 5 x Confidence 4 / Effort 2 = 10.0`, keep.

## Validation

- `python -m py_compile python/franken_networkx/__init__.py tests/python/test_tree_kcomponents_assortativity_conformance.py tests/artifacts/perf/20260609T-k-components-jfsyo-boldfalcon/harness_kcomponents_residual.py`
- `python -m pytest tests/python/test_tree_kcomponents_assortativity_conformance.py -q -k k_components` -> `60 passed, 49 deselected`
- `harness_kcomponents_residual.py proof` -> unchanged SHA above
- `sha256sum -c proof_files.sha256` -> all OK
- `git diff --check` -> passed
- `rch exec -- cargo check -p fnx-python --all-targets --features pyo3/abi3-py310` -> passed on `ovh-a`
- `ubs tests/python/test_tree_kcomponents_assortativity_conformance.py tests/artifacts/perf/20260609T-k-components-jfsyo-boldfalcon/harness_kcomponents_residual.py` -> 0 critical, 0 warning

Blocked by pre-existing unrelated Rust drift:

- `cargo fmt -p fnx-python --check` reports formatting diffs in untouched Rust
  files under `crates/fnx-python/src/`.
- `cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings`
  is blocked by existing `fnx-generators` unused-result warnings.
- Broad `ubs python/franken_networkx/__init__.py` timed out after 120s without
  emitted findings; focused UBS and parity/proof gates covered this change.
