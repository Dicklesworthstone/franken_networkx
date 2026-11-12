# br-r37-c1-dptts PageRank Wrapper Scan Decision

Profile-backed target:
- Bead claim: `pagerank(BA(2000,4,seed=42) weighted)` was reported as 3.95x slower than NetworkX.
- Fresh baseline on this checkout: fnx mean `0.008161488142962168s`; NetworkX mean `0.005878082854906097s`; digest `c992e25715a2cdcd5ed3da2fe2976bfb5f647994d6bccdce37523048a985180e`.
- Fresh hyperfine baseline: `471.7 ms +/- 22.2 ms`.
- Fresh profile: `_pagerank_scipy` dominated PageRank time; `adjacency_arrays` cost `0.321s/81 calls`; `graph_has_nonfinite_edge_weight` cost `0.211s/81 calls`; sync cost was only `0.045s/81 calls`.

Rejected lever 1:
- Lever: fuse nonfinite-weight parity detection into a PageRank-specific native COO extractor.
- Digest after: `c992e25715a2cdcd5ed3da2fe2976bfb5f647994d6bccdce37523048a985180e`.
- Hyperfine after: `500.5 ms +/- 24.8 ms`, slower than baseline.
- Verdict: rejected and reverted.

Rejected lever 2:
- Lever: route weighted undirected Graph PageRank through existing default-order adjacency arrays to skip nodelist canonicalization and per-edge string index lookups.
- Digest after: `c992e25715a2cdcd5ed3da2fe2976bfb5f647994d6bccdce37523048a985180e`.
- Hyperfine after: `498.9 ms +/- 24.4 ms`, slower than baseline.
- Verdict: rejected and reverted.

Behavior proof:
- Output ordering remains node insertion order in `dict(zip(nodelist, ...))`.
- Tie-breaking and graph traversal ordering are unchanged because no source code was kept.
- Floating point operation order in the shipped code is unchanged because both candidates were reverted.
- RNG is fixed to NetworkX BA seed `42` in the benchmark; library PageRank path itself is deterministic.
- Golden-output sha256 stayed `c992e25715a2cdcd5ed3da2fe2976bfb5f647994d6bccdce37523048a985180e` for every candidate run.

Close reason:
- The bead's original 3.95x gap is stale on this checkout; fresh gap is about 1.39x.
- Two profile-backed single-lever candidates failed the Score >= 2.0 keep gate, so no source change is retained for this bead.
