# br-r37-c1-baqyi — add_edges_from/add_edge partial-error-state parity

## Scope discovered (bead said DiGraph; probe found 4 shapes x 4 classes)
1. DiGraph non-dict third: nx creates BOTH endpoint nodes before
   dict.update raises (PyGraph had the fix since br-edges3rd; the
   DiGraph binding never got it).
2. Multi 3-tuple semantics: nx tries ddd.update(dd) FIRST — dict-able
   iterables of pairs are DATA ([('a',3)] adds an attributed edge!);
   only TypeError/ValueError makes the third the key. fnx keyed
   everything non-dict (silently wrong RESULTS, not just errors).
3. Multi unhashable key: nx creates nodes before the TypeError; fnx's
   Python wrapper hash(key) guard + both Rust bindings raised first
   (also left node_key_map/inner INCONSISTENT in MultiDiGraph).
4. Multi non-dict 4th: nx raises BEFORE add_edge (nothing created);
   fnx silently ignored the 4th and ADDED the edge. In the ctor this
   wraps as NetworkXError('Input is not a valid edge list').

## Fixes
- digraph.rs PyDiGraph add_edges_from: pre-add nodes (port of the
  PyGraph idiom).
- _multi_add_edges_from (Python): mirrors nx's parse loop verbatim
  (try-update-first, ddd built BEFORE add_edge, partial-pair merge
  retention).
- Multi add_edge wrapper + both Rust add_edge bindings: nodes created
  when the explicit key is unhashable (consistency + parity).
- Both Multi ctor absorb loops + add_edges_from 4-branches: throwaway
  dict.update before add_edge; ctor maps via edge_list_err.

## Proof
46-case battery (errors + node/edge state + attrs + parallel-key
regression) sha 658c6073; 42 committed tests; full pytest 21709
passed, 0 failed (incl. the ctor regression-lock file that caught a
mid-fix over-raise).
