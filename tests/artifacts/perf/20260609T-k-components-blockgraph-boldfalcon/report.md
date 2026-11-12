# br-r37-c1-04z53.61 - k_components clique-block lattice

## Target

Profile-backed continuation after complete, cycle, and forest `k_components`
certificates. Barbell/block graphs still delegated to NetworkX
`k_components`, spending the profile in `node_connectivity`,
`build_residual_network`, and `all_node_cuts` even though each nontrivial
biconnected block is a clique and has a closed-form k-component lattice.

One lever only: certify simple undirected block graphs with native
`biconnected_components` plus clique edge counts, then emit the closed-form
Moody-White lattice in NetworkX order.

## Proof

- Golden proof SHA256: `9530ffe397815c9b998df96a0dcbd823d32d17fd23c3c6e488314dba1cdf3a81`
- Baseline proof SHA matched after proof SHA.
- Cases: `barbell4_1`, `barbell5_2`, bowtie, `K4` joined to triangle, and a
  non-clique biconnected block that must delegate.
- Isomorphism: output key order, value list type, component set type, component
  membership, and closed-form tie ordering match NetworkX.
- Floating point: N/A.
- RNG: N/A.

## Benchmark

Command family:

```bash
VIRTUAL_ENV=/data/projects/.scratch/venvs/fnx-lnrxj-boldfalcon \
PATH=/data/projects/.scratch/venvs/fnx-lnrxj-boldfalcon/bin:$PATH \
rch exec -- hyperfine --warmup 1 --runs 5 \
  'python tests/artifacts/perf/20260609T-k-components-blockgraph-boldfalcon/harness_blockgraph_k_components.py time --n 100 --repeats 5 --which fnx'
```

Results:

- Baseline FNX: `885.6 ms +- 23.2 ms` mean, `888.5 ms` median.
- After FNX: `329.5 ms +- 10.5 ms` mean, `329.8 ms` median.
- Genuine NetworkX comparator: `844.7 ms +- 64.1 ms` mean, `836.3 ms` median.
- Self speedup: `2.69x` by mean.
- After vs genuine NetworkX: `2.56x` faster by mean.
- Score: Impact 3 x Confidence 3 / Effort 1 = `9.0`, keep.

Profile delta:

- Baseline: `1,125,591` calls in `0.285 s`, dominated by
  `_call_networkx_for_parity`, `node_connectivity`, residual network
  construction, and `all_node_cuts`.
- After: `13,570` calls in `0.018 s`, dominated by two native-backed block
  edge-count checks and native `biconnected_components`.

## Validation

- `pytest tests/python/test_tree_kcomponents_assortativity_conformance.py -q`:
  `99 passed, 3 warnings`.
- `python -m py_compile python/franken_networkx/__init__.py tests/python/test_tree_kcomponents_assortativity_conformance.py tests/artifacts/perf/20260609T-k-components-blockgraph-boldfalcon/harness_blockgraph_k_components.py`: passed.
- `ubs tests/python/test_tree_kcomponents_assortativity_conformance.py tests/artifacts/perf/20260609T-k-components-blockgraph-boldfalcon/harness_blockgraph_k_components.py`: passed.
- `timeout 180s ubs python/franken_networkx/__init__.py`: timed out without
  emitted findings.
- `CARGO_TARGET_DIR=/data/projects/rch_target_franken_networkx_boldfalcon_blockgraph_check rch exec -- cargo check -p fnx-python --all-targets`: passed with existing `fnx-generators` unused-must-use warnings.
- `cargo fmt -p fnx-python --check`: failed on pre-existing untouched Rust
  formatting drift in `crates/fnx-python/src/{algorithms.rs,digraph.rs,lib.rs,readwrite.rs}`.
- `CARGO_TARGET_DIR=/data/projects/rch_target_franken_networkx_boldfalcon_blockgraph_clippy rch exec -- cargo clippy -p fnx-python --all-targets --no-deps -- -D warnings`: failed on pre-existing untouched `collapsible_if` lints in
  `crates/fnx-python/src/{digraph.rs,lib.rs}` plus existing generator warnings.
