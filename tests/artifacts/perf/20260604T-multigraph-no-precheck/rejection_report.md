# br-r37-c1-zqupd: rejected no-precheck fresh-edge lever

## Target

- Profile-backed residual after `6ef1a977f`: `entry_probe_profile_multigraph_int_keys_after.txt` still showed `_fast_add_explicit_int_edge` at `1.351s` over 450000 calls.
- Candidate lever: remove the outer Python-binding `inner.has_edge` precheck and let `MultiGraph::add_fresh_edge_unrecorded` own occupied-bucket rejection.

## Result

The source lever was removed. Golden output stayed unchanged, but the measured win did not meet the keep bar.

| Measurement | Baseline | Candidate | Delta |
| --- | ---: | ---: | ---: |
| Direct FNX mean | `0.2149757692s` | `0.2569058919s` | regression |
| Direct FNX median | `0.1983838030s` | `0.2489957070s` | regression |
| Hyperfine mean | `1.2007137388s` | `1.1912011646s` | `1.008x` |
| Golden digest | `6041eefb1e549a77af5c18a4e08ab1dc24e9df42e2e9ef094e810d35bedf58dc` | same | unchanged |

Score: below 2.0. Do not keep.

## Proof And Pivot

- Behavior proof during the candidate run: output digest stayed byte-identical and matched NetworkX for `multigraph_int_keys`.
- Revert proof: `crates/fnx-python/src/lib.rs` has no diff after manual restoration and `maturin develop --release --features pyo3/abi3-py310` rebuilt the restored module.
- Next primitive: stop probing this same control-flow seam. Attack integer-slot fresh-edge construction with order-preserving Python object side tables so the hot path stops round-tripping through string-keyed node/edge maps for exact integer construction.
