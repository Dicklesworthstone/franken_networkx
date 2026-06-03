# quotient_graph edge bucket isomorphism proof

Behavior contract:

- Preserve default `quotient_graph` node labels as partition frozensets.
- Preserve block insertion order.
- Preserve quotient edge insertion order for the first successful undirected block-pair orientation.
- Preserve default edge attribute shape and integer/default weight totals.
- Preserve default node attrs: `graph`, `nnodes`, `nedges`, and `density`.
- Preserve NetworkX parity for the deterministic workload.
- Avoid changing directed, multigraph, custom relation/data, explicit `create_using`, and non-integer explicit weighted semantics.

Golden digest:

- `3b82f51eccda8bd9a2f0a24657abf67f8bb2bc9b9da8e49d136f6089b31be62a`

Digest inputs:

- Ordered quotient nodes, excluding the opaque subgraph object but including `nnodes`, `nedges`, and `density`.
- Ordered quotient edges, including sorted endpoint block contents and sorted edge attributes.

Digest result:

- Baseline FNX digest: `3b82f51eccda8bd9a2f0a24657abf67f8bb2bc9b9da8e49d136f6089b31be62a`
- Baseline NetworkX digest: `3b82f51eccda8bd9a2f0a24657abf67f8bb2bc9b9da8e49d136f6089b31be62a`
- After FNX digest: `3b82f51eccda8bd9a2f0a24657abf67f8bb2bc9b9da8e49d136f6089b31be62a`
- After NetworkX digest: `3b82f51eccda8bd9a2f0a24657abf67f8bb2bc9b9da8e49d136f6089b31be62a`

Ordering/tie-breaking/RNG:

- RNG seed fixed at `12345` in the harness.
- Partition construction is deterministic ascending contiguous blocks.
- The fast path stores bucket totals in a map but emits edges by ascending partition-pair order, matching the old first-insertion order.
- No tie-break policy changed.

Floating point:

- The fast path rejects explicit non-integer weight values and falls back to the previous exact pair-scan implementation.
- This avoids floating-point summation-order drift.

Golden-output verification:

- `baseline_bench.jsonl` and `after_bench.jsonl` contain matching FNX and NetworkX digests.
- `artifact_sha256.txt` covers all proof, benchmark, profile, and validation artifacts in this directory.
