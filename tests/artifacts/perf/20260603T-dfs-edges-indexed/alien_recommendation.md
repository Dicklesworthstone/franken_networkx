# Alien primitive selection

Directive inputs:

- `/data/projects/alien_cs_graveyard/alien_cs_graveyard.md`
- `/data/projects/alien_cs_graveyard/high_level_summary_*.md`
- `/data/projects/.scratch/no_gaps_directive.txt`

The selected primitive is an index-space traversal kernel: move the hot DFS loop from string-keyed, allocation-heavy graph access into dense integer graph traversal while preserving the public string-label output contract.

This is the GraphBLAS-style lesson applied at traversal scale: once the graph is already resident in indexed adjacency, run the kernel over integer adjacency and materialize labels only at the boundary.

Rejected alternatives for this pass:

- Parallel DFS: changes ordering and tie-breaking risk, not suitable for strict NetworkX order preservation.
- SIMD scanning: no profile evidence that byte scanning is the bottleneck.
- Global CSR rebuild: broader surface than needed for this one lever and not required to remove the observed string-key/neighbor-allocation tax.

Next deeper candidate after this pass: split the undirected `Graph` harmonic centrality path to a dense forward-adjacency kernel if current profile data still shows reverse-adjacency/string-index overhead after re-profiling.

