# Alien Primitive

Source: `/alien-graveyard` and `/alien-artifact-coding` pass for graph conversion/matrix construction.

Primitive selected: zero-copy-ish edge-stream reuse from an existing native materializer rather than per-edge Python adjacency wrapper traversal.

This is an arena/zero-copy framing style lever: reuse a native edge tuple stream that already preserves graph edge order and Python node objects, then keep the existing NumPy accumulation semantics. The next deeper primitive for this lane is a fully native sparse/dense matrix fill kernel that writes directly into NumPy buffers without materializing Python edge tuples.
