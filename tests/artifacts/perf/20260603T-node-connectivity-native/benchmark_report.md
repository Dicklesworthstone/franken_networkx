# br-r37-c1-w3yng benchmark report

## Target

- Kernel: `fnx.node_connectivity(Graph)` -> native `_fnx.node_connectivity`.
- Graph: deterministic NetworkX 400-node, degree-4 regular graph, seed `8675309`.
- Profile-backed hotspot: baseline cProfile spent `0.668s / 0.679s` in native `_fnx.node_connectivity`.

## Lever

Build the undirected node-split auxiliary residual once in `global_node_connectivity`, then clone it for each pair-local max-flow. The residual topology is graph-only; pair state starts when `aux_max_flow` mutates the clone.

## Baseline

- Hyperfine: `1.02711060008s +/- 0.11870580699s`, median `0.99413530898s`.
- Direct FNX sample: `0.62092530500s`, value `4`, digest `bbf21a609465999089e8d8f8c525e4235fd561c464d915517e0f6d65063ecb98`.
- Direct NX sample: `0.46908267602s`, value `4`, same digest.
- cProfile: `0.66911839799s` elapsed; native `_fnx.node_connectivity` `0.668s`.

## After

- Hyperfine: `0.94279924476s +/- 0.02099953630s`, median `0.94449218206s`.
- Direct FNX 3-sample mean: `0.64184633667s`, value `4`, digest `bbf21a609465999089e8d8f8c525e4235fd561c464d915517e0f6d65063ecb98`.
- Direct NX 3-sample mean: `0.48401499700s`, value `4`, same digest.
- cProfile: `0.65041864401s` elapsed; native `_fnx.node_connectivity` `0.649s`.

## Delta

- Hyperfine mean: `1.02711060008s -> 0.94279924476s`, `8.21%` faster, `1.089x`.
- cProfile native: `0.668s -> 0.649s`, `2.84%` faster.
- Behavior: integer value and graph/result digest unchanged.

## Score gate

- Impact: 3
- Confidence: 3
- Effort: 1
- Score: `3 * 3 / 1 = 9.0`

Decision: keep and commit.
