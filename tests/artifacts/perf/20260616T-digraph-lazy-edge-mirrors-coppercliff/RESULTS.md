# br-r37-c1-04z53.9123 DiGraph lazy edge-data mirrors

Status: rejected, evidence-only closeout.

Target:
- Profile-backed hotspot: post-9122 `digraph_attr` construction residual.
- Baseline profile: `_try_add_edges_from_batch` 1.492s / 200 loops, `_native_edges_with_data` 0.573s / 200 loops, total 9.454s / 200 loops.

Lever tested:
- For fresh exact-int, string-keyed `DiGraph.add_edges_from((u, v, dict), ...)`, keep attrs in the Rust inner graph and defer Python edge-data mirror dict creation until observable edge-data APIs need it.
- Duplicate directed pairs and non-string attr-key batches fell back to the existing eager mirror path to preserve NetworkX merge and key behavior.

Behavior proof:
- Existing focused parity: `rch exec -- env PYTHONPATH=python .venv/bin/pytest tests/python/test_add_edges_attr_batch_parity.py -q`
- Result: 25 passed.
- Golden proof: `candidate_lazy_mirror_golden.json`
- Golden sha256: `961efcbc1df101dd94341ca88101c32b155a97bcd6c9de2d946169271107bec8`
- Preserved: node order, directed edge order, source-dict non-aliasing, weighted reads, live materialized dict mutation, no RNG, no floating-point reassociation in construction.

Benchmark result:
- Baseline direct survey FNX median: 0.008804291021078825s
- After direct survey FNX median: 0.008386399014852941s
- Baseline direct survey ratio FNX/NX: 1.2771886607425644x
- After direct survey ratio FNX/NX: 1.1549371008539862x
- Baseline hyperfine FNX mean: 2.13242892672s
- After hyperfine FNX mean: 2.3015422210600005s
- Baseline profile total: 9.454s / 200 loops
- After profile total: 9.122s / 200 loops
- After profile `_try_add_edges_from_batch`: 1.228s / 200 loops
- After profile `_native_edges_with_data`: 1.232s / 200 loops

Decision:
- Rejected, Score < 2.0.
- The construction function itself got faster, but the benchmarked user-visible workflow immediately enumerates `edges(data=True)` for digesting. The lever moves Python dict materialization out of construction and into the first edge-data observation, creating a mixed result with a hyperfine regression. This is not a robust campaign keep.

Next routing:
- Do not repeat lazy mirror materialization for this target.
- Attack a deeper construction primitive: avoid Python-level edge-data digest/materialization costs with a batched native edge-data snapshot path or structurally reduce attr conversion work without deferred mirror debt.
