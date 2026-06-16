# Graph.neighbors native-method rejection

Bead: `br-r37-c1-graph-neighbor-native-method-coppercliff`

Target: `[list(G.neighbors(n)) for n in G.nodes()]` on
`Graph(gnp_random_graph(n=2400, p=0.0045, seed=23))`, after `c02f3f208`
and the evidence-only native-row rejection `e3fffed08`.

## Profile-backed target

Selector still put `graph_neighbors_all` at the top non-construction residual:

- FNX `0.0028605145s/loop`, NetworkX `0.0014138844s/loop`, ratio `2.02x`.
- Output SHA matched NetworkX:
  `b99171852c6eeb1d713fec332be3c5adae9270e08127abedd6b2ac02014954f4`.
- cProfile over 160 loops: `0.891s` total, `0.628s` cumulative in the Python
  `Graph.neighbors` wrapper.

## Lever Tried

Change the dispatch shape: add a Rust `_native_neighbors_iter(n)` method with
PyO3 signature `(n)` and temporarily assign default `Graph.neighbors` directly
to that native method. To preserve private NetworkX-style storage semantics, the
candidate also installed an instance-level Python fallback when `Graph._adj` or
`Graph._node` was assigned.

## Behavior proof

Golden SHA unchanged:
`8a7cee6e5b434f5edb0dc27317191196e3463b00abedb8558870f3ecc26cd378`.

Unchanged surfaces:

- Neighbor row output SHA:
  `b99171852c6eeb1d713fec332be3c5adae9270e08127abedd6b2ac02014954f4`.
- Missing-node exception:
  `NetworkXError("The node missing is not in the graph.")`.
- Unhashable-node exception:
  `TypeError("unhashable type: 'list'")`.
- Active row iterator mutation:
  `RuntimeError("dictionary changed size during iteration")`.
- Private `_adj` override fallback order: `[2, 1]`.
- `inspect.signature(G.neighbors)` preserved parameter `n`; `G.neighbors(n=1)`
  and `dict_keyiterator` type smoke checks passed.
- No floating-point, RNG, or algorithmic tie-breaking surface was touched.

## Benchmarks

RCH hyperfine, loop300:

| command | baseline mean | candidate mean | result |
| --- | ---: | ---: | ---: |
| FNX | `0.9928300418s +/- 0.0301743972s` | `1.0008329117s +/- 0.0339865512s` | `0.99x` |
| NetworkX | `0.7720889256s +/- 0.0317509262s` | `0.7730737088s +/- 0.0396737140s` | comparator flat |

Focused gap worsened from `1.286x` to `1.295x`.

Direct timer, loop200, was favorable but not accepted because RCH did not
confirm it:

| command | baseline s/loop | candidate s/loop | result |
| --- | ---: | ---: | ---: |
| FNX | `0.001752398010` | `0.001615858400` | `1.08x` |
| NetworkX | `0.000768639520` | `0.000804751580` | comparator moved |

cProfile, 100 loops:

- Total: `0.359s -> 0.214s`.
- Python wrapper disappeared; native `_native_neighbors_iter` cumulative:
  `0.101s`.

Rejected. Source restored to the `c02f3f208` row-cache implementation. Score:
`Impact 0 x Confidence 5 / Effort 3 = 0.0`.

Next route: stop tuning `Graph.neighbors` per-call dispatch. Attack a different
primitive: batch/all-row neighbor extraction for algorithms that consume every
row, or move a concrete graph algorithm off per-node Python API calls.
