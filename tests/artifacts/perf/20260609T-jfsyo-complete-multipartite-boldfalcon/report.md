# br-r37-c1-jfsyo - complete multipartite k_components certificate

## Target

Pass 37 kept lever for the non-forest `k_components` residual on
`origin/main` `b5d463fc14dbd04a89494df6b8be3bb68d8a289b`.

Current FNX already has closed-form certificates for complete graphs, simple
cycles, forests, and clique-block graphs. Complete multipartite connected
components were still delegating into NetworkX's Moody-White / Kanevsky
`all_node_cuts` path even though their k-component lattice is closed form.

## Lever

Add a simple-Graph certificate for connected complete multipartite components
when `flow_func is None` and no self-loops exist.

For each connected component, nodes are partitioned by identical non-neighbor
sets. The graph is accepted only if every part is an independent set and every
node connects to every node outside its part. The component connectivity is
`|V| - max_part_size`, so the component appears at every level from that value
down to 1. If any component fails the certificate, FNX delegates unchanged.

Custom `flow_func` calls still delegate because genuine NetworkX calls the
flow function for complete multipartite graphs.

## Baseline

Direct baseline:

| Case | Baseline FNX | Genuine NX | Ratio |
| --- | ---: | ---: | ---: |
| complete multipartite 3x6, 18 nodes | `595.15 ms` | `620.85 ms` | `0.96x` |
| complete multipartite 3x8, 24 nodes | `14.501 s` | `13.071 s` | `1.11x` |

Hyperfine baseline, 18 nodes:

| Command | Mean | Median |
| --- | ---: | ---: |
| FNX public `k_components` | `987.2 ms` | recorded in `baseline_hyperfine_multipartite6.json` |
| Genuine NX `orig_func` | `892.7 ms` | recorded in `baseline_hyperfine_multipartite6.json` |

Profile baseline on 18 nodes: `fnx.k_components` spends `1.570 s` in
`_call_networkx_for_parity`, then NetworkX `k_components`; `all_node_cuts`
accounts for `1.538 s`, and `dag.antichains` for `0.652 s`.

## After

Direct after:

| Case | Baseline FNX | After FNX | Speedup |
| --- | ---: | ---: | ---: |
| complete multipartite 3x6, 18 nodes | `589.65 ms` | `0.246 ms` | `2395x` |
| complete multipartite 3x8, 24 nodes | `14.501 s` | `0.541 ms` | `26799x` |

Hyperfine after, 18 nodes:

| Command | Mean | Median |
| --- | ---: | ---: |
| FNX public `k_components` | `304.5 ms` | recorded in `final_hyperfine_multipartite6.json` |
| Genuine NX `orig_func` | `952.5 ms` | recorded in `final_hyperfine_multipartite6.json` |

The single-call hyperfine includes process startup/import overhead. The direct
in-process timing captures the actual algorithmic win.

## Proof

- Baseline proof SHA: `63ac97842d7588b44dc3e99fdda9b0d2214180a646fb03b2795eeb16d45e9d0d`
- After proof SHA: `63ac97842d7588b44dc3e99fdda9b0d2214180a646fb03b2795eeb16d45e9d0d`
- Final proof SHA: `cf0f31b7312df821747b0e4c085b6c0829e4ffed6dbedfa7ca362b9673674e20`
- `sha256sum -c proof_files.sha256`: passed
- Focused pytest: `33 passed, 49 deselected`

Isomorphism notes:

- Ordering preserved: k levels descend from connectivity to 1. Levels above 2
  prepend exact-k components before carried higher-k components, while levels 2
  and 1 use connected-component order, matching NetworkX reconstruction.
- Tie-breaking unchanged: accepted components have one maximal component per k
  level; missing-cross-edge cases delegate.
- Floating point: N/A.
- RNG: N/A.
- Custom flow function: delegates and raises the same sentinel as NetworkX.

## Gates

- `py_compile`: passed for wrapper, focused tests, and harness.
- `git diff --check`: passed.
- `pytest tests/python/test_tree_kcomponents_assortativity_conformance.py -q -k 'k_components'`: passed.
- `rch exec -- cargo check -p fnx-python --all-targets --features pyo3/abi3-py310`: passed with pre-existing `fnx-generators` `unused_must_use` warnings.
- `rch exec -- cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings`: blocked by the same pre-existing `fnx-generators` warnings.
- `cargo fmt -p fnx-python --check`: blocked by pre-existing Rust formatting drift outside this Python-only patch.
- `ubs tests/python/test_tree_kcomponents_assortativity_conformance.py tests/artifacts/perf/20260609T-jfsyo-complete-multipartite-boldfalcon/harness_kcomponents_multipartite.py`: passed with 0 critical and 0 warning issues.
- `timeout 180s ubs python/franken_networkx/__init__.py ...`: timed out on the large wrapper before emitting findings.

## Score

Impact `5` x Confidence `5` / Effort `2` = `12.5`.

## Reprofile

The separate residual bundle
`tests/artifacts/perf/20260609T-k-components-jfsyo-boldfalcon/` measures
non-multipartite chorded-cycle / separation-pair cases after this pass. Those
still delegate and show the real next primitive: native k=2 separation-pair /
SPQR-style cohesive-blocking with NetworkX-order partition emission.
