# Harmonic Centrality Rejected Lever

Bead: `br-r37-c1-45n6t`

Profile-backed target: `harmonic_centrality_generic<fnx_classes::Graph>` on sparse graph `n=1600`, average degree `5`.

Harvested primitive: GraphBLAS-style BFS/frontier traversal from `/data/projects/alien_cs_graveyard/alien_cs_graveyard.md`, lines 3516-3537. The relevant idea is to make repeated graph traversals reuse compact frontier state and avoid needless per-source allocation.

Candidate lever: replace per-source `Vec<Option<usize>>` style distance state with a reusable `Vec<usize>` distance buffer plus generation stamps and a cleared `VecDeque`.

Result: rejected. The direct rch harness regressed from `61.2789 ms/iter` to `97.7786 ms/iter`, with checksum unchanged at `2790554.746032` and golden SHA unchanged.

Next implication: do not repeat this exact generation-stamp lever without a new profile. The next plausible target needs a different profile-backed lever, likely queue/frontier representation, reverse-adjacency shape, or graph-index lookup during reverse adjacency construction.
