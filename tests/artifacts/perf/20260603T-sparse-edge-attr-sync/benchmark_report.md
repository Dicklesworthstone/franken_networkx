# Sparse Weighted Edge-Only Attr Sync

Bead: `br-r37-c1-oymqq`

## Target

Profile-backed target: `to_scipy_sparse_array(Graph, weight="weight", dtype=None, format="csr")` on `barabasi_albert_graph(8000, 4, seed=42)`.

Baseline cProfile showed the sparse weighted route spending `0.032s` over 12 calls in `_sync_rust_edge_attrs` / `_fnx_sync_attrs_to_inner` even though this export only reads edge weights. The full attr sync rebuilt node attrs before the edge-dirty check.

## Lever

Add an edge-only Rust sync entrypoint for simple `Graph` / `DiGraph` Python bindings and route native weighted sparse export through `_sync_rust_edge_attrs(G, edge_only=True)`.

This is one lever: skip node attr rebuild on edge-weight-only sparse matrix kernels while preserving the existing full sync path elsewhere.

## Results

Direct operation sample, 15 repeats:

| Metric | Baseline | After | Delta |
| --- | ---: | ---: | ---: |
| FNX mean | `0.014587645801172281s` | `0.012729135532087337s` | `1.146x` faster |
| FNX median | `0.014426092995563522s` | `0.012573207990499213s` | `1.147x` faster |
| NX mean | `0.025704026602519057s` | `0.02682325613568537s` | reference only |
| CSR digest | `12d41580d0336461201dbaa08fecc5250eab75162c958f5a91da80875db1ab37` | `12d41580d0336461201dbaa08fecc5250eab75162c958f5a91da80875db1ab37` | unchanged |

cProfile, 12 measured calls:

| Frame | Baseline cumulative | After cumulative |
| --- | ---: | ---: |
| `measure` total | `0.184s` | `0.167s` |
| `to_scipy_sparse_array` | `0.174s` | `0.156s` |
| `_sync_rust_edge_attrs` | `0.032s` | `0.000s` |
| `_fnx_sync_attrs_to_inner` | `0.032s` | absent from hot path |
| `adjacency_default_order_typed_arrays` | `0.070s` | `0.075s` |

Hyperfine process envelope, 25 runs:

| Metric | Baseline | After |
| --- | ---: | ---: |
| Mean | `0.8805329283399999s` | `0.8682897172999999s` |
| Median | `0.86498027802s` | `0.8738970051s` |
| Min | `0.82933671002s` | `0.7919395681s` |

One after-confirm hyperfine run had host outliers (`0.90055052886s` to `2.71368887686s`, mean `1.10342264486s`); the repeat returned a stable process envelope and is the retained after envelope.

## Score

Impact `3` x Confidence `4` / Effort `2` = `6.0`.

Keep decision: retained. The isolated operation and cProfile show a real win, the process envelope repeat is slightly faster, and the behavior digest is unchanged.

## Artifacts

- Baseline sample: `baseline_to_scipy_weighted_both.jsonl`
- After sample: `after_confirm_to_scipy_weighted_both.jsonl`
- Baseline profile: `profile_baseline_to_scipy_weighted_fnx.txt`
- After profile: `profile_after_confirm_to_scipy_weighted_fnx.txt`
- Baseline hyperfine: `hyperfine_baseline_to_scipy_weighted.json`
- After hyperfine: `hyperfine_after_confirm2_to_scipy_weighted.json`
