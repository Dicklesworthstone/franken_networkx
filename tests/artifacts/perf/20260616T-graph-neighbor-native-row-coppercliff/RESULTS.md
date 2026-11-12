# Graph.neighbors native-row rejection

Bead: `br-r37-c1-graph-neighbor-native-row-coppercliff`

Target: `[list(G.neighbors(n)) for n in G.nodes()]` on
`Graph(gnp_random_graph(n=2400, p=0.0045, seed=23))`, after commit
`c02f3f208`.

## Profile-backed target

Fresh selector after the row-cache keep still put `graph_neighbors_all` at the
top non-construction residual:

- FNX `0.0028605145s/loop`, NetworkX `0.0014138844s/loop`, ratio `2.02x`.
- Output SHA matched NetworkX:
  `b99171852c6eeb1d713fec332be3c5adae9270e08127abedd6b2ac02014954f4`.
- cProfile over 160 loops: `0.891s` total, `0.628s` cumulative in
  `Graph.neighbors`, dominated by Python wrapper/cache dispatch.

## Lever Tried

Replace the simple `Graph.neighbors` no-private-storage path with direct native
live-row dict iteration:

```python
hash(n)
return iter(self._native_adjacency_row_dict(n))
```

The eager `hash(n)` was required to preserve NetworkX's unhashable-node
`TypeError`; without it, the native binding mapped the list input to a missing
node `NetworkXError`.

## Behavior proof

After repairing the hash guard, golden SHA was unchanged:
`516ad47facf5cf86cade0bb8ec8fd77863104349445edea0e49519e9b57f1180`.

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
- No floating-point, RNG, or algorithmic tie-breaking surface was touched.

## Benchmarks

RCH hyperfine, loop300:

| command | baseline mean | candidate mean | result |
| --- | ---: | ---: | ---: |
| FNX | `0.9912808127s +/- 0.0377599034s` | `1.0095318019s +/- 0.0232502549s` | `0.98x` |
| NetworkX | `0.7341347163s +/- 0.0166001829s` | `0.7428764230s +/- 0.0226373089s` | comparator flat |

Focused gap worsened from `1.350x` to `1.359x`.

Direct timer, loop200, was favorable but not accepted because the required RCH
gate did not confirm it:

| command | baseline s/loop | candidate s/loop | result |
| --- | ---: | ---: | ---: |
| FNX | `0.002227822665` | `0.001613780955` | `1.38x` |
| NetworkX | `0.000927325565` | `0.000782674185` | comparator moved |

cProfile, 100 loops:

- Total: `0.440s -> 0.375s`.
- `Graph.neighbors` cumulative: `0.271s -> 0.255s`.

Rejected. Source restored to the `c02f3f208` row-cache implementation. Score:
`Impact 0 x Confidence 5 / Effort 2 = 0.0`.

Next route: this residual needs a different primitive than per-call native-row
dispatch, likely a batch/all-neighbor row extraction path or algorithm callers
that avoid per-node Python method dispatch entirely.
