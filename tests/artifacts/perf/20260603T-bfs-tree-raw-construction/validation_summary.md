# bfs_tree raw construction candidate validation

Recorded:

- rch baseline direct FNX/NetworkX sample.
- rch baseline cProfile.
- rch baseline hyperfine.
- rch candidate rebuild via `maturin develop --release --features pyo3/abi3-py310`.
- rch candidate direct FNX/NetworkX sample.
- rch candidate cProfile.
- rch candidate hyperfine.
- rch restored rebuild via `maturin develop --release --features pyo3/abi3-py310`.
- rch restored FNX sample.

Result:

- Candidate failed the performance gate and was removed.
- Golden digest stayed unchanged across baseline, candidate, NetworkX, and restored runs.
- Source restoration checks passed.

No kept source means no code validation gate is claimed for this rejected candidate beyond the restored release rebuild and source-diff absence check.
