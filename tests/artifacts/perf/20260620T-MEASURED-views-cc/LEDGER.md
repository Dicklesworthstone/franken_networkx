# MEASURED warm bench — view-materialization + conversion surface (br-r37-c1-measuredviews)

- Agent: `BlackThrush` · 2026-06-20 · warm min-of-12/15 pinned, existing install. n=400, m=1500,
  node attr 'v' + edge attr(s). nx/fnx = nx_time/fnx_time (>1 = fnx WINS).

## WINS (fnx > nx)
| function                 | nx/fnx | |
|--------------------------|--------|--|
| to_dict_of_lists         | 2.66x  | native bulk |
| to_dict_of_dicts (conv)  | 1.48x  | native |
| get_node_attributes('v') | 1.42x  | native attr-presence path |
| list(edges(data=True))   | 1.18x  | |
| to_dict_of_dicts         | 0.97x  | neutral |

## SUBSTRATE-BOUND LOSSES (edge/node-attr view materialization — NOT code-only-fixable)
| function                 | nx/fnx | abs (fnx/nx ms) | note |
|--------------------------|--------|-----------------|------|
| get_edge_attributes('w') | 0.72x  | 0.529 / 0.379   | iterates the edge-data view; nx reads inline adj dict. data=name switch measured only ~3% (sentinel-complex to preserve present-None semantics) -> ~0-gain, not shipped |
| dict(adjacency())        | 0.55x  | 0.015 / 0.008   | sub-microsecond; adjacency view materialization |
| list(nodes(data=True))   | 0.82x  | 0.005 / 0.004   | sub-microsecond |

## Findings
- get_edge_attributes: VALUE-correct vs nx incl. present-None edge attrs (installed nx
  includes present attrs whose value is None; fnx matches — verified Graph/DiGraph/Multi).
  The residual perf gap is the per-edge edge-attr VIEW crossing vs nx's inline dict —
  substrate (needs the persistent ordered edge-attr mirror, same class as 4b5ie/9hkgu).
- dict(adjacency()) / nodes(data=True): real ratio losses but sub-microsecond absolute;
  not worth a Python-mirror cache (complexity > benefit at these sizes).

No code-only lever here (the meaningful gap, get_edge_attributes, is substrate-bound and
its data=name micro-opt is ~0-gain). Recorded for the eventual edge-attr-mirror Rust work.
