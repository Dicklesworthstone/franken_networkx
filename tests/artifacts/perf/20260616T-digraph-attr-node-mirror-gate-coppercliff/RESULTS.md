# br-r37-c1-u8lxy DiGraph attributed node-mirror gate probe

## Target

`DiGraph.add_edges_from([(u, v, {"weight": 1.0}), ...])`

This was a profile-backed construction residual outside BoldFalcon's active
`graph_attr` bead. The candidate idea was to gate inactive
`node_iter_mirror_insert` work in the fresh exact-int attributed `DiGraph`
batch path.

## Baseline

- Direct survey FNX median: `0.008750543 s`.
- Direct survey NetworkX median: `0.006522110 s`.
- Golden digest: `3f1de3be563f8e8f7a63710ca7bea1886888bd83417fcdade9249eee112d9d1c`.
- rch hyperfine loop160 FNX mean: `6.547006348240001 s`.
- rch hyperfine loop160 NetworkX mean: `4.39961434264 s`.
- Profile over 200 loops: `_try_add_edges_from_batch` `1.409 s`; `_native_edges_with_data` `0.575 s`.

## Verdict

Rejected before source edits. Inspection showed the proposed inactive
node-iterator mirror gate is already present in the current `PyDiGraph` fresh
exact-int attributed batch. Source was untouched; route to a different primitive.
