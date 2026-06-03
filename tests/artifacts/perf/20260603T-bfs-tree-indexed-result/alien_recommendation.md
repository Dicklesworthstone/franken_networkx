# Alien primitive note

The rejected candidate applied the batching/locality primitive from the alien-graveyard pass: keep traversal in index space and materialize object labels only at the result boundary.

That primitive was correct but not deep enough for this residual. The remaining process-level cost did not move materially after removing the intermediate edge string stream.

Next direction should be a different primitive, not another construction micro-tweak:

- Native tree view/result representation that defers Python attr dict creation until observation.
- A specialized immutable BFS tree object with NetworkX-compatible `nodes()` and `edges()` views.
- Or a deeper source-level target after re-profiling a broader residual surface.

No source from this candidate was kept.

