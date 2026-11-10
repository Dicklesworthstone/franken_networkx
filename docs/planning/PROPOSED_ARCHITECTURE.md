# PROPOSED_ARCHITECTURE

## 1. Architecture Principles

1. Spec-first implementation, no line translation.
2. Strict mode for compatibility; hardened mode for defensive operation.
3. RaptorQ sidecars for long-lived conformance and benchmark artifacts.
4. Profile-first optimization with behavior proof artifacts.

## 1.1 Porting-to-Rust Application Mode

Current execution mode follows the skill decision tree as:

- phase 4 (implementation from spec) for active packet development
- phase 5 (conformance/QA) continuously in parallel via packet and readiness gates

Implementation protocol:

1. derive module responsibilities from `EXISTING_NETWORKX_STRUCTURE.md` and packet contract rows.
2. implement in Rust crate seams below.
3. validate with deterministic fixture replay and parity artifacts before advancing breadth.

## 2. Crate Map

- `fnx-classes`: Graph/DiGraph/MultiGraph core.
- `fnx-views`: adjacency/report view contracts.
- `fnx-dispatch`: dispatchable/decorator backend routing.
- `fnx-convert`: ingestion and conversion utilities.
- `fnx-algorithms`: shortest-path/flow/components core.
- `fnx-generators`: deterministic/random graph generators.
- `fnx-readwrite`: adjlist/edgelist/json/graphml scoped IO.
- `fnx-durability`: RaptorQ sidecar generation, scrub verification, decode proof artifacts.
- `fnx-conformance`: curated Rust evidence harness and fixture replay.
- `fnx-runtime`: strict/hardened policy + evidence ledger.

## 2.1 External Leverage (FrankenSuite)

- `asupersync` integration point lives in `fnx-runtime` feature: `asupersync-integration`.
- `frankentui` integration point lives in `fnx-runtime` feature: `ftui-integration`.
- FrankenSQLite reference spec copied to:
  - `reference_specs/COMPREHENSIVE_SPEC_FOR_FRANKENSQLITE_V1.md`

## 3. Runtime Plan

- API layer normalizes inputs and validates invariants.
- Planner/dispatcher selects algorithm implementation.
- Core engine executes with explicit invariant checks.
- Canonical parity gate runs through the installed Python surface.
- Conformance adapter replays curated oracle fixtures and captures evidence.
- Evidence layer emits parity reports, benchmark deltas, and decode proofs.

## 3.1 Module Boundary and Ownership Contract

| Boundary | Public API seam | Internal ownership seam | Verification seam |
|---|---|---|---|
| `fnx-classes` | graph mutation/query interfaces | adjacency storage + revision counters | graph-core conformance fixtures |
| `fnx-views` | projection/read view interfaces | cache invalidation + coherence internals | `generated/view_neighbors_strict.json` |
| `fnx-dispatch` | route decision interface | backend ranking/tie-break internals | dispatch strict fixtures + policy logs |
| `fnx-convert` + `fnx-readwrite` | conversion/IO entry interfaces | parser normalization + warning budget internals | convert/readwrite parity fixtures |
| `fnx-algorithms` | algorithm APIs + witness payloads | traversal/work-queue internals | differential fixtures + witness checks |
| `fnx-conformance` | packet/run harness interfaces | mismatch taxonomy + forensics links | smoke/readiness/e2e gates |

## 4. Compatibility and Security

- strict mode: maximize scoped behavioral parity.
- hardened mode: same outward contract plus bounded defensive checks.
- fail-closed on unknown incompatible metadata/protocol fields.

## 5. Performance Contract

- baseline, profile, one-lever optimization, verify parity, re-baseline.
- p95/p99 and memory budgets enforced in CI.

## 6. Conformance Contract

The Python capacity-scaling flow seam owns an indexed residual network in
`_capacity_scaling.py`. Node imbalances/potentials and paired residual arcs
live in arrays; ordered neighbor groups retain the public tie-break contract.
The wrapper preserves caller graph and heap protocols, and the solver neither
constructs a NetworkX residual graph nor substitutes the simplex algorithm.
This module isolates the algorithm from graph storage and provides a future
native-kernel boundary without changing the public API.

The Python minimum-cycle-basis seam owns its de Pina solver in
`_minimum_cycle_basis.py`. Integer indices keep lifted nodes separate from
user labels, while shared exact Kruskal and Dijkstra primitives preserve
numeric arithmetic and tied-path ordering. Native and optional SciPy routes
are admitted only for supported exact domains; the public wrapper retains
backend validation and graph-family rejection order.

The Bellman-Ford predecessor wrapper owns option routing. Ordinary exact
simple graphs with the literal default `heuristic=False` and compatible
logical storage retain their bulk weight snapshot/count-only implementation.
Requested heuristics, multigraphs, subclasses/views, callable weights, and
assigned private rows use the existing owned live-row relaxation engine.
Public self-loop checks and full reachable-map target semantics are shared;
there is no second heuristic loop or new native kernel.

The owned readwrite module normalizes iterable line sources lazily and parses
records directly into the caller's graph. Existing compressed-path and decoded
line helpers own opened handles; caller-supplied streams retain their lifetime.
Weighted and multiline writers share an incremental encoded-line sink.
Ordinary native file routes remain independent. Insertion completes before
advancing an arbitrary input iterator; completed plain adjacency rows can use
the existing batch API when its original method and ordinary labels make that
safe. No cross-record buffer or NetworkX parser delegation is introduced.

The Louvain fallback lives in `_louvain.py`, with indexed level state and
ordered sparse neighbor rows. It owns node moves, modularity stopping, and
coarsening while streaming moves into the existing partition-set replay.
The community wrappers retain the native kernel for ordinary inputs and
admit custom graph/numeric/random protocols to the owned level iterator.
Its suspension boundary is also the random-draw and graph-snapshot boundary;
finishing a level does not eagerly compute the next one. Degree and size
retain their shared exact numeric routes, including the native live-mirror
refresh that rejects unsupported scalar types before using stored floats.

The complete GraphML decoder lives in `readwrite.GraphMLReader`. It interprets
ElementTree records directly into FrankenNetworkX graph storage, including
multiedges, defaults, type callbacks, and yFiles data. String/file wrappers own
their distinct namespace recovery and stream lifetimes. Native simple-document
admission and the hardened validation/recovery ledger remain separate routes;
the complete decoder no longer rebuilds a NetworkX graph.

Connectivity's Python orchestration composes the owned auxiliary builders,
flow solvers, and local cut/connectivity helpers. Global custom-solver queries
reuse one auxiliary/residual pair. Connectivity-specific cut extraction owns
the residual mutation/replay protocol, while standalone minimum-cut extraction
keeps its non-mutating contract. Existing ordinary native routes remain intact.

Node and edge betweenness wrappers share the shortest-path live-row
admission predicate before graph conversion. Existing owned Brandes engines
handle callback-sensitive traversals, private adjacency and asymmetric
undirected views while preserving caller mappings, arithmetic and RNG state.
Ordinary native routes remain separate.

Flow solvers consume original graph protocols and caller-owned residuals.
Residual construction is the boundary that reads input edge data when
no residual is supplied. Custom node-connectivity orchestration follows the
same public-protocol path as edge connectivity, while native paths keep
their existing graph admission. No persistent adjacency cache is introduced.

Backend graph conversion uses native bulk snapshots only for ordinary
concrete storage. Private mappings and views use public rows, with node,
successor and predecessor ordering restored independently before returning
the converted graph.

The complete GEXF decoder lives in `readwrite.GEXFReader`, sharing version and
scalar type declarations with the owned GEXF writer. It constructs native
graph objects without a NetworkX graph intermediary. Existing payload
admission and native policy/recovery routes select when the complete decoder
is needed, while public reader methods retain configurable decoding hooks.

The owned GML token/stack decoder separates lexical parsing from graph
construction in the existing readwrite module. Strict full-grammar reads
construct FrankenNetworkX graphs directly, without a NetworkX intermediary
or a parse/write/reparse admission roundtrip. Explicit native modes and
hardened recovery retain their established policy boundary.

Minimum-cost flow wrappers share the owned simplex solve boundary and
consume its cost/flow result directly. The extraction adapter separates
ordinary native bulk storage from live public graph providers; wrappers do
not duplicate validation, repair numeric types or rescore a solved flow.
Bulk admission checks the selected scalar domains without invoking custom
numeric methods, keeping later self-loop reads live for observable protocols.

Weighted asynchronous label propagation separates encountered-label state
from numeric accumulation in its sparse indexed loop. Snapshot admission is
shared with fast label propagation and excludes observable custom graph,
weight and random protocols, which use the existing owned live traversal.
The shared edge-data view preserves node-bunch orientation for every
attribute selector and projects values lazily within live adjacency rows.

Weighted distance wrappers and backend source recovery share the existing
live-row admission predicate. Spanning-edge wrappers keep caller inputs until
advancement and select their existing owned engines for public protocols;
native selector admission is checked against concrete storage at that point.
No new graph cache or duplicate shortest-path/spanning algorithm is added.

Negative-cycle witnesses reuse the same live Bellman-Ford relaxation engine
as weighted path queries. Only predecessor reconstruction remains specific
to the witness API; no cached weighted-row copy or second detector is kept.

Closeness, harmonic centrality, Wiener index and closeness vitality share
that weighted-query admission before graph coercion. Their owned distance
consumers retain the reference copy or view boundaries, including directed
closeness's reverse copy and vitality's removed-node subgraph views.

Iterative spectral wrappers admit native and sparse arithmetic before
coercion and retain their existing owned iterations for observable graph,
vector and numeric providers. Eigenvector and Katz keep their distinct
weight-selector semantics rather than sharing a lossy matrix interpretation.

Flow hierarchy retains graph-size and induced-component-size operations
when an edge-only aggregate would change floating arithmetic or custom
provider behavior. Its component traversal remains the existing owned SCC
implementation.
Filtered and reverse views implement weighted size through their public
degree traversal, preserving accumulation order and exact numeric domains.
Backend dispatch exposes both capacity scaling and flow hierarchy through
the same pre-conversion provider boundary used by iterative ranking calls.

Graph-source constructors admit native absorb only for authoritative native
storage. The public-protocol route uses the existing owned adjacency decoder
for every source/target graph-kind combination, then applies shallow graph
and node attributes and explicit overrides. This keeps conversion ordering,
parallel-key merging and factory behavior in one implementation.
The decoder retains batch insertion for ordinary mappings and consumes
observable mapping providers incrementally without a second constructor
implementation.
The simple-to-undirected-multigraph absorb route shares existing scalar
attribute admission rather than allowing its lazy native mirror to replace
non-round-trippable Python values.
Flow extraction and graph conversion share admission for plain attribute
reads, including owned write-watched dictionaries whose read methods remain
builtin. Caller overrides select the public route on the next operation.

The incremental spanning-tree frontier serves both Graph and MultiGraph.
Parallel-edge partitions retain the full `(u, v, key)` identity and use the
owned Kruskal selector; ordinary simple graphs retain native selection.
Each yielded graph owns clean attributes without partition bookkeeping,
and consuming a prefix selects only the necessary frontier candidates.

Greedy modularity's complete fallback lives beside its native adapter in
`community.py`. It owns sparse gain tables, indexed row heaps and the merge
frontier, with original graph/numeric protocols at its input boundary.
Backend routing preserves those inputs before conversion; ordinary primitive
inputs retain the existing native kernel. No upstream solver or intermediate
NetworkX graph is required for the fallback.

- `tests/python/` is the canonical source of truth for public,
  NetworkX-observable behavior.
- feature-family fixtures captured from legacy oracle.
- `fnx-conformance` replays a curated subset to produce machine-readable
  parity/evidence reports per run.
- regression corpus for previously observed mismatches.

## 7. Current Vertical Slice (Implemented)

- deterministic undirected graph core in `fnx-classes`:
  - node/edge mutation,
  - attribute merge semantics,
  - deterministic insertion ordering.
- decision-theoretic strict/hardened runtime policy with evidence ledger in `fnx-runtime`.
- deterministic unweighted shortest path + connected components/component-count witnesses in `fnx-algorithms`.
- deterministic degree-centrality with explicit score-order contract in `fnx-algorithms`.
- deterministic closeness-centrality with NetworkX-aligned WF-improved semantics in `fnx-algorithms`.
- deterministic and seeded graph generators with strict/hardened guards in `fnx-generators`.
- cycle-generator insertion policy aligned with legacy edge-order behavior for larger `n`.
- fixture-driven conformance evidence harness with drift detection in `fnx-conformance`.
- conformance expansion for component, generator, and centrality fixture operations (14-fixture corpus).
- durability sidecar pipeline in `fnx-durability` + `scripts/run_conformance_with_durability.sh`.
- view layer with revision-aware cache invalidation in `fnx-views`.
- percentile benchmark gate pipeline in `scripts/run_benchmark_gate.sh`.
