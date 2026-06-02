# Alien recommendation card: conversion-view empty base

Bead: `br-r37-c1-y2b8t`

## Symptom

`Graph.to_directed(as_view=True)` and `DiGraph.to_undirected(as_view=True)` build
live views, but their dynamic classes also inherit the canonical PyO3
`Graph`/`DiGraph` base for `isinstance` parity. Without a local `__new__`, Python
routes construction into the PyO3 base with the parent graph argument, copying
the source graph into dead Rust storage. Every observable conversion-view method
answers through `_graph`, so that base copy is pure construction overhead.

Profile-backed target:

- Direct rch sample, `graph_to_directed`, `n=1000`, `degree=4`, `calls=50`:
  `0.02008656938s` per call on the old constructor path.
- Hyperfine rch process benchmark: old constructor command mean `1.3921046396s`.

## Graveyard match

Primitive: lazy zero-copy view with structural sharing.

Relevant buried-CS matches from `/data/projects/alien_cs_graveyard/alien_cs_graveyard.md`:

- Zero-copy transfer: avoid copying backing storage when ownership or access can
  be represented by a typed handle.
- Persistent/structurally shared data structures: preserve visible state by
  sharing the unchanged backing representation rather than cloning the whole
  structure.
- Selection-vector style views: represent a derived view by indirection into
  the source instead of materializing filtered or transformed tuples.

## Recommendation

Add `_ConversionGraphViewBase.__new__` and return `super().__new__(cls)` without
passing the parent graph. That allocates the mixed PyO3 base as an empty graph in
O(1), then `__init__` wires the live view to the source graph through `_graph`.

This is the same safe-Rust-compatible primitive used by the prior
`_FilteredGraphView.__new__` fix: preserve `isinstance` behavior while preventing
the backing Rust graph from receiving a parent graph copy it never observes.

## Expected value

- Impact: 5. Converts an O(|V| + |E|) constructor to O(1) on a public view path.
- Confidence: 5. Every relevant query method is already overridden to read from
  `_graph`; direct golden digests are identical old/new.
- Effort: 1. One local constructor override.
- Score: 25.0.

## Fallback

If a future PyO3 base constructor changes and `super().__new__(cls)` no longer
allocates an empty graph, use an explicit Python factory that creates the
conversion view through `object.__new__` plus a minimal initialized empty base,
then keep the same golden snapshot tests around nodes, edges, degree, size,
`has_edge`, and `copy()`.
