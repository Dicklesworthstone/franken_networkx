# Reality Check Bridge Plan — 2026-04-08

> **Status:** Phase 2 (bridge plan) → revised in-place across Phase 4 ambition rounds.
> **Source assessment:** in-conversation reality check, branch `main`, commit ecb229e.
> **Method:** README/SPEC/AGENTS vision extraction + deep code investigation + live smoke + full pytest suite + beads history audit.

---

## 0. Corrected baseline (after beads history audit)

- **What works:** standalone API, NX backend mode (narrow dispatch dict), 1392/0/54 Python parity tests, real Rust core (39,691 LOC algorithms + 12,008 LOC bindings + 551 GIL releases + zero NX callbacks), MultiGraph/MultiDiGraph parity, RaptorQ encode/decode mechanism, edgelist/adjlist/JSON/GraphML/GML parsers, working benchmark gate script.
- **Beads is alive:** 217 closed issues; the team has been closing `NX-REPLACE` fallback elimination, backend dispatch fixes, SLO threshold work, MultiGraph eulerian bug, and stochastic_block_model native fast path *today and yesterday*. The empty open queue means we're between work waves, not abandoned.
- **What is genuinely still missing:** the surrounding "system" the SPEC sells — CGSE engine, strict/hardened mode dispatch, conformance harness freshness, SLO restoration vs. the 30× relaxation in commit 742c48e, fuzz/adversarial coverage of every parser, repo hygiene (war zone of agent debug scripts in root), durability coverage of fixture bundles, structured evidence ledger, G1→G8 CI enforcement.
- **Process problems:** AGENTS.md "No Script-Based Changes" rule actively violated by ~24 root-level `fix_*.py` / `find_*.py` / `patch_*.py` scripts; ~75 root-level `test_*.py` / `test_*.rs` ad-hoc files; 27 MB of stale UBS / clippy / bug-scan dumps; `algorithms.rs.bak` and `chunk{,1,2,3}.txt` fragments inside the package directory.

---

## 1. Gap inventory (what the bridge must close)

| ID | Category | Gap | Severity |
|---|---|---|---|
| G-CGSE | Vision/Stub | "Canonical Graph Semantics Engine" exists only as JSON schemas + enum constants. No tie-break decision dispatch, no complexity witness emission, no per-family policy lookup. README's headline differentiator. | **Critical** |
| G-MODE | Vision/Stub | `CompatibilityMode::{Strict, Hardened}` and `DecisionAction::{Allow,FullValidate,FailClosed}` exist as enums; no algorithm/parser branches on them; no test verifies divergence. | **Critical** |
| G-CONF-FRESH | Stale/Proof | `artifacts/conformance/latest/` has six 140-byte report stubs from Mar 19 vs. code edited Apr 8. The Rust harness has been silently superseded by the Python pytest suite without any of the spec's required artifact contracts (RaptorQ envelope, deterministic replay, normalized parity reports). | **Critical** |
| G-CONF-DOC | Doc Drift | FEATURE_PARITY claims "59 fixtures across 12 E2E journeys"; actual fresh evidence: zero. SPEC §15 conformance matrix is unmet. | High |
| G-SLO | Performance/Regressed | Commit 742c48e relaxed SLOs: serialization 45 → 1.5 MB/s (30×), memory 220 → 400 MB, p99 tail 650 → 2000 ms. SPEC §17 budgets are no longer enforced anywhere. | **Critical** |
| G-CI-GATES | Integration | SPEC §18 prescribes G1→G8 fail-closed release-blocking gates; no `.github/workflows/` enforces them. `crates/fnx-conformance/tests/ci_gate_topology_gate.rs` is local-only. | **Critical** |
| G-LEDGER | Stub | "Decision-theoretic evidence ledger" types exist in `fnx-runtime`; no algorithm writes to them. SPEC §6 alien-artifact decision contract is unmet. | High |
| G-FUZZ | Partial | Only `adjlist` fuzz target is fresh (commit ecb229e). edgelist/graphml/gml/json parsers lack adversarial fuzz harnesses despite SPEC §5 mandating them for high-risk parsers. | High |
| G-DURABILITY-COV | Partial | RaptorQ wraps JSON metadata reports only — not the actual graph fixtures, benchmark binaries, or migration manifests SPEC §9 enumerates. | High |
| G-REPO-HYGIENE | Discipline/Violated | ~24 `fix_*.py`/`find_*.py`/`patch_*.py`, ~75 root `test_*.py`, 27 MB UBS dumps, `algorithms.rs.bak`, `chunk*.txt` inside package, all violating AGENTS.md L137-152. None gitignored. | **Critical** |
| G-TONX-RESIDUE | Implementation | 15 `_to_nx` references and 4 `_networkx_compat_graph` proxy refs remain in `python/franken_networkx/__init__.py` despite the recent NX-REPLACE wave. 10 modified test files uncommitted. | High |
| G-BACKEND-AUTO | Integration | `backend.py:_SUPPORTED_ALGORITHMS` is a hand-curated dict; new algorithms in Rust do not auto-extend backend dispatch. NX backend mode silently falls back for everything not in the dict. | High |
| G-FEATURE-PARITY-DOC | Doc Drift | FEATURE_PARITY.md marks 13 of 14 families `in_progress`; claims like "I/O coverage ~56%", "100% top-level function parity (731+)" are not backed by a generated coverage matrix in the repo. | Medium |
| G-README-STATE | Doc Drift | README "Current State" lists 7 vertical slices that are 6 months old and pre-date 90% of the algorithm corpus. README "Next Steps" items 1-5 are stale. | Medium |
| G-TEST-SKIPS | Proof | 54 tests in the Python suite are currently skipped. Each skip is either (a) a known gap, (b) an untracked TODO, or (c) a flake — needs categorization + bead-tracking. | Medium |
| G-ROOT-TESTS | Discipline | ~75 ad-hoc `test_*.py`/`test_*.rs` files in repo root that are NOT collected by pytest, NOT in `tests/python/`, and likely orphaned. Either promote to tests or delete. | High |
| G-CHANGELOG-FRESH | Doc Drift | `CHANGELOG.md` (41 KB) was last touched 2026-03-22; no entries for the wave of NX-REPLACE / backend / SLO work since. | Low |
| G-DOCS-EMPTY-FAILURE | Spec | SPEC §4 fail-closed-on-unknown rule is implemented nowhere — unknown format metadata loads silently. | Medium |
| G-VIEW-CACHE-COHERENCE | Proof | `fnx-views` provides revision-aware cache invalidation, but conformance fixtures for view coherence (per SPEC §15) are stale. | Medium |
| G-COND-DRIFT-LEDGER | Stub | "Compatibility drift report" / "drift ledger" mentioned in SPEC §16, AGENTS.md, FEATURE_PARITY — no actual ledger artifact emitted by current builds. | Medium |
| G-MEM-HARDEN | Performance | Memory regression budget was doubled (220 → 400 MB); no profiling/explanation accompanies the relaxation. SPEC §7 acceptance rule requires correctness evidence. | Medium |

**Total gaps: 21** (5 critical, 8 high, 6 medium, 1 low, 1 doc-only).

---

## 2. Bridge plan — five tracks

### Track A — Process & hygiene reset (unblocks everything else)

| Bead | Title | Outcome |
|---|---|---|
| A1 | Repo root cleanup: stage `fix_*.py`/`find_*.py`/`patch_*.py`/`*.bak`/`chunk*.txt`/UBS dumps for deletion or move under `scripts/dev/` after explicit user permission per AGENTS.md Rule 1 | Repo root contains only first-party project files |
| A2 | `.gitignore` audit: add `*.bak`, `clippy_output.txt`, `*ubs*.txt`, `errors.json`, `rust-bug-scan.txt`, `dist/`, `fuzz/target/`, `target/`, `.venv/`, `.benchmarks/`, `.hypothesis/`, `.ruff_cache/`, `python/franken_networkx/_fnx.abi3.so`, `python/franken_networkx/__pycache__/` | Working tree clean after a fresh build |
| A3 | Promote or delete the ~75 ad-hoc `test_*.py`/`test_*.rs` in repo root; any that exercise unique behavior must move into `tests/python/` and become part of the parity gate | Pytest collects every retained test |
| A4 | Commit the 10 in-flight test files in `tests/python/` (modified-but-uncommitted), or revert if obsolete | `git status` clean |
| A5 | Resolve `crates/fnx-python/src/algorithms.rs.bak`: diff vs. live, decide which to keep, then delete the other (with permission) | Single canonical algorithms.rs |
| A6 | `br doctor` SQL/JSONL sync repair (the WAL-without-SHM warning + the stale-list bug) | `br list` returns the same set as the JSONL |

### Track B — Conformance & evidence restoration (unblocks Gate A claim)

**Ambition note (round 2):** the simple "regenerate the corpus and gate freshness" plan is necessary but not sufficient. The SPEC's assurance ladder (§8) is Tier A → Tier B → Tier C → Tier D. Today the project has Tier A (1392 pytest unit/integration assertions) and pretends to have Tier B (the Rust harness is stale). Tier C (property/fuzz/adversarial) is shallow, Tier D (regression corpus for historical failures) is missing. The expanded plan rebuilds the harness as a *layered* system where each tier is independently auditable, *and* introduces metamorphic testing to handle the algorithm-output oracle problem on graphs where the answer isn't known.

| Bead | Title | Outcome |
|---|---|---|
| B1 | Decide canonical conformance source. **Recommended:** Python pytest is the active Tier B; Rust harness is retired in favor of a thin Rust *driver* that calls into pytest and consumes its JSON report. SPEC §8/§15/§18 and FEATURE_PARITY rewritten accordingly. | Single source of truth declared, no two-pipeline drift |
| B2 | Tier B regeneration: re-run `fnx-conformance` (or its successor) against current `main`; regenerate ALL fixture reports under `artifacts/conformance/latest/`; every report carries `{schema_version, fixture_id, fnx_commit, nx_version, status, mismatches[], duration_ms, witness_hash}`. | Fresh evidence bundle, every report < 24h at commit time |
| B3 | Tier B RaptorQ envelope (SPEC §19) on every report — `source_hash` + `repair_symbols` + `symbol_hashes[]` + `scrub.status` per fixture. The envelope schema is enforced by `crates/fnx-conformance/tests/envelope_schema_gate.rs`. | Every report has a verifiable sidecar |
| B4 | **Freshness gate**: CI fails if any `*.report.json` under `artifacts/conformance/latest/` is older than the most recent change to `crates/fnx-conformance/`, `crates/fnx-algorithms/`, or `python/franken_networkx/`. The gate is the first thing G2 runs. | Stale evidence is impossible to commit |
| B5 | Tier C — **structure-aware property suite** via `proptest`. For each algorithm family, define an invariant (e.g. "shortest path is monotone in edge weight", "max matching is at least as large as maximal matching", "PageRank sums to 1.0 ± ε"); run 1000 random graphs per family per CI run; minimize and quarantine on failure. This is the spec's Tier C, currently absent. | Property-level proofs for every family |
| B6 | Tier C — **metamorphic testing** for algorithms where the oracle is itself uncertain: e.g. "adding an isolated vertex to G must not change pagerank values for existing vertices (only normalize them)" and "permuting node labels and re-running must produce a permutation-equivalent output." 6 metamorphic relations per family minimum. Catches drift NX-comparison can't catch. | Oracle-free correctness proofs |
| B7 | Tier C — **differential fuzzing** between fnx and NX on randomly generated graphs (cargo-fuzz + python harness). Any output divergence auto-creates a beads issue with the minimized graph as a fixture. This is the spec's "differential conformance" promise made *ongoing*, not snapshot. | Drift detection becomes continuous |
| B8 | Tier D — **historical regression corpus**. Every fixture that has ever caught a bug stays in `crates/fnx-conformance/fixtures/regressions/<bead-id>/`, with provenance to the originating beads issue. CI runs the full regression corpus on every PR. The corpus only grows. | Past bugs cannot recur silently |
| B9 | Cross-walk: every Python parity test emits a normalized parity record consumable by the Rust driver (or the Rust harness consumes pytest JSON output). One pipeline, not two. | Single source of conformance truth |
| B10 | View-coherence fixtures (SPEC §15 row 2) — the only "high"-severity row currently absent from the corpus. Includes mutation-during-iteration cases, cache invalidation under concurrent reads, and revision-counter monotonicity. | View cache coherence proven |
| B11 | **Conformance dashboard**: a generated `artifacts/conformance/dashboard.html` showing per-family pass rate, drift count, freshness, sidecar status. Linked from README. Public-facing trust signal. | Conformance state is at-a-glance |

### Track C — CGSE crown jewel realization (or honest retraction)

**Ambition note (round 1):** the bare-bones C1-C6 below would technically discharge the README claim, but it would still be just "policies + witnesses with sidecars" — the kind of thing any port could bolt on. To be the project's actual differentiator, CGSE has to do something *no other NetworkX port can do*: make the ordering choices and the cost model **machine-checkable** against the upstream oracle, and **generate counter-examples automatically** when an algorithm's emergent ordering drifts from its declared policy. The expanded plan below pushes the engine from "metadata layer" to "decision-theoretic conformance kernel."

| Bead | Title | Outcome |
|---|---|---|
| C1 | **Decision point** — implement (recommended) vs. retract. If retracting, rewrite README §"What Makes This Project Special" + SPEC §0/§14 references and stop claiming a crown jewel. | Either a real engine or honest docs |
| C2 | New `fnx-cgse` crate. Define `TieBreakPolicy` as a sum type with **at least 12** instantiations so every NetworkX-observable ordering quirk has a name: `LexMin`, `LexMax`, `InsertionOrder`, `ReverseInsertionOrder`, `WeightThenLex`, `LexThenWeight`, `DeterministicHashSeeded(u64)`, `DegreeMinThenLex`, `DegreeMaxThenLex`, `DfsPreorder`, `BfsLevelLex`, `EdgeKeyLex`. Each algorithm family declares its policy as a const type parameter so policy-mismatch is a compile error. | Policies are first-class data and *type-checked* per algorithm family |
| C3 | `ComplexityWitness { n, m, dominant_term: Symbol, observed_count: u64, policy_id: PolicyId, seed: Option<u64>, decision_path_blake3: [u8; 32] }`. Every algorithm in the scoped families emits one per call into a per-thread ring buffer flushed to a `WitnessLedger`. The `decision_path_blake3` is a Merkle hash over every tie-break decision the algorithm took, in order — so two runs that take the same path on the same graph produce identical hashes, and any drift is detectable as a hash mismatch. | Witnesses include a *cryptographic decision-path fingerprint*, not just a count |
| C4 | Wire 12 reference algorithms through CGSE (one per policy variant): dijkstra, bellman_ford, bfs, dfs, max_weight_matching, min_weight_matching, connected_components, strongly_connected_components, kruskal, prim, eulerian_circuit, topological_sort. Each algorithm acquires a `&mut WitnessSink` via the runtime, calls it on every tie-break, and the call site is checked at compile time against the declared policy. | 12 algorithms produce inspectable + Merkle-hashed witnesses |
| C5 | **Adversarial tie-break corpus**: a generator (seeded, deterministic) that builds graphs maximizing the number of equal-cost / equal-weight ties for each algorithm family. At least 50 graphs per family. For each, run NetworkX as oracle and FrankenNetworkX side-by-side; assert path equality AND witness-hash equality. This is the test that turns CGSE from "we have a policy" into "we proved the policy is what NX does." | Tie-break determinism *and* identity to NetworkX proven across 600+ adversarial cases |
| C6 | **Counter-example mining loop**: nightly CI job runs a property-based search (using `proptest`) for any graph where fnx and NX disagree on tie-break order. Any disagreement auto-creates a beads issue, attaches the minimized graph as a fixture, and quarantines the algorithm until resolved. | CGSE drift is impossible to miss |
| C7 | Per-family witness artifacts under `artifacts/cgse/witnesses/<family>/<date>.witnesses.jsonl` with RaptorQ sidecars per SPEC §19; the "complexity witness artifacts per algorithm family" claim becomes literally true. Witnesses become first-class evidence in the conformance bundle. | Crown jewel becomes *load-bearing*, not decorative |
| C8 | **Complexity oracle**: derive an analytic complexity formula for each algorithm family (e.g. `dijkstra: O((n+m) log n)`) and assert that the observed witness counts stay within a constant factor of the formula across the corpus. Any drift fails the build. This is the spec's "complexity regressions for adversarial classes" gate (SPEC §17) made literal. | Complexity regressions become a CI gate |
| C9 | **Public CGSE API**: expose the witness ledger to Python so users can `with fnx.cgse.witness_capture() as w: fnx.dijkstra(G)` and inspect what tie-break decisions were taken. This is a feature *no other NetworkX port has*. | CGSE is a user-visible product feature, not just internal plumbing |

### Track D — Strict/Hardened mode wiring (or honest retraction)

**Ambition note (round 1):** the simple "two enums + four fixtures each" plan below is the literal reading of SPEC §4 — but the SPEC is itself borrowing from the frankenlibc/frankenfs tradition, where mode separation is **decision-theoretic**: Strict minimizes expected loss under a "trust the input" prior, Hardened minimizes expected loss under an "input is adversarial" prior, and the policy boundary between them is *learned* from past incidents in a drift ledger. The expanded plan turns the modes into a Bayesian admission controller with calibrated confidence and explicit loss matrices, per SPEC §6 (the alien-artifact decision contract) — which is currently zero-implemented.

**Decision update (2026-04-15):** D1 is resolved in favor of implementation, not
retraction. The existing `CompatibilityMode` + `CgsePolicyEngine` surface in
`fnx-runtime` is now the canonical boundary; the remaining Track D beads are
about wiring that policy through parser/high-risk entry points and proving the
observable strict/hardened behavior with fixtures and ledgers.

| Bead | Title | Outcome |
|---|---|---|
| D1 | Decision point: implement (recommended) vs. retract. SPEC §4 + §16 makes this central. | Decision documented |
| D2 | Implement mode dispatch in `fnx-runtime`: a `RuntimePolicy { mode, allowlist, decision_log, posterior, loss_matrix }` value threaded through every parser (`fnx-readwrite`) and high-risk algorithm. The policy is *not* a global; it is constructed per-call per SPEC §6 evidence contract, so mode behavior is reproducible from logs. | Real dispatch surface, no hidden global state |
| D3 | Strict-mode behavior: every parser fail-closes on unknown metadata fields (SPEC §16 row "unknown format metadata"); every dispatch falls back to fail-closed unless allowlisted. Add **24** strict fixtures (6 per format × 4 formats: `.gml`, `.graphml`, `.json`, `.adjlist`) proving fail-closed on malformed inputs. | Strict mode behavior locked across all parsers |
| D4 | Hardened-mode behavior: **bounded recovery via Bayesian admission controller**. The controller maintains a posterior `P(input_safe \| evidence)` updated from parser warnings, attribute-shape anomalies, and graph-density anomalies. The recovery action is the one minimizing expected loss under SPEC §16's threat-cost matrix. 24 hardened fixtures prove same inputs recover with audit trail and updated posterior. | Hardened mode is observable, *and* its decisions are derivable from the policy |
| D5 | **Loss matrix** (SPEC §6 row 3): explicit asymmetric costs encoded as `LossMatrix { false_accept_cost, false_reject_cost, late_detect_cost, recovery_cost }` per parser × per attack class. Calibrated against the adversarial fixture corpus, not guessed. | Decisions are *justified* by data |
| D6 | **Calibrated confidence** (SPEC §6 row 4-5): every recovery decision emits a calibrated `confidence: f32` field. CI gate: aggregate Brier score across the adversarial corpus < 0.10, monitored by a drift alarm that opens a beads issue if it crosses threshold. | Confidence is calibrated, not asserted |
| D7 | Decision ledger: every mode-mediated decision writes a structured record `{ts, parser, mode, evidence_signals, posterior_before, posterior_after, action, confidence, loss_estimate}` to `artifacts/conformance/latest/decision_ledger.jsonl` with RaptorQ sidecar. The ledger schema is versioned and validated by `crates/fnx-conformance` on every CI run. | Ledger is alive, schema-checked, durably stored |
| D8 | **Drift ledger feedback**: weekly CI job reads the decision ledger, identifies decision clusters where confidence < 0.5, and creates beads issues to expand fixture coverage in the under-confident region. This closes the "explicit drift ledger" loop SPEC §16 prescribes. | Hardening is data-driven, not vibes-driven |
| D9 | Conformance: each mode runs the full smoke + readiness gates; reports are mode-stamped (`*.strict.report.json`, `*.hardened.report.json`); divergence between modes is itself a tracked metric. | Both modes proven, *and* their divergence is bounded |

### Track E — Performance, durability, fuzz, CI gates

**Ambition note (round 1):** the SPEC's perf section asks for "p95/p99 budgets" — table stakes for any port. The expanded plan below applies the project's own `extreme-software-optimization` methodological DNA: profile-first, single-lever, behavior-isomorphism proof, re-baseline. Each perf bead must close that loop, not just measure once.

| Bead | Title | Outcome |
|---|---|---|
| E1 | **Restore SLOs to SPEC §17 values**: revert commit 742c48e relaxations. If any one is genuinely unachievable, write an explicit `artifacts/perf/slo_downgrade_rationale_<row>.md` with: (1) flamegraph evidence of the bottleneck, (2) the optimization levers tried, (3) the behavior-isomorphism proof per SPEC §7, (4) the user-impact analysis, (5) the new budget. Per-row downgrades only. No blanket relaxation. | Honest performance bar |
| E2 | Benchmark workloads for the 8 SLO rows (verify `franken_networkx-16ds` actually closed this; if not, finish it). Each workload uses *adversarial* graph classes per SPEC §17 — power-law degree, max-density, expander, path-like — not just gnp. | Every SLO is exercised on graphs that *can* break it |
| E3 | **Profile-and-prove optimization loop** for each SLO row that misses: (1) baseline percentiles, (2) `cargo flamegraph` profile committed under `artifacts/perf/proof/<bead>/flamegraph.svg`, (3) one-lever change, (4) behavior-isomorphism proof from the conformance corpus, (5) re-baseline percentiles, (6) delta artifact. SPEC §7 mandates this loop; today only 1 proof artifact exists (`artifacts/perf/proof/2026-02-14_graph_kernel_clone_elision.md`). Need at least 8 — one per SLO row. | Every optimization carries proof |
| E4 | Wire `scripts/run_benchmark_gate.sh` into `.github/workflows/perf.yml` — fail-closed on regression, attach percentile artifacts, post diff-vs-baseline as PR comment. Includes `regression_envelope.json` per SPEC §18. | Perf gate enforced in CI, visible per PR |
| E5 | Wire `crates/fnx-conformance/tests/ci_gate_topology_gate.rs` into `.github/workflows/conformance.yml` — runs G1→G8 in order, short-circuits on first miss, emits failure envelope with deterministic-replay command per SPEC §18 ordering rule. | G1→G8 enforced, failures reproducible |
| E6 | **Cargo-fuzz harnesses for every parser**: `edgelist_fuzz`, `graphml_fuzz`, `gml_fuzz`, `json_fuzz`, `pajek_fuzz`, `node_link_fuzz`, plus `attribute_value_fuzz` for type-confusion attacks. Each runs 60s in PR CI, 24h on nightly. Crash corpus committed under `fuzz/corpus/<target>/`. | All parsers fuzzed continuously |
| E7 | **Structure-aware fuzzers** using `arbitrary::Arbitrary` for graph types, so the fuzzer generates valid-but-pathological graphs and exercises algorithm code paths the parser fuzzers can't reach. One target per algorithm family. | Algorithm-level fuzz coverage |
| E8 | **RaptorQ-everywhere coverage expansion**: sidecars for fixture bundles in `crates/fnx-conformance/fixtures/`, benchmark percentile JSONs, migration manifests (`artifacts/migrations/*.json`), reproducibility ledgers, `CHANGELOG.md`, the SPEC itself. Per SPEC §9 every long-lived artifact gets a sidecar. CI gate: every file under `artifacts/` matching the durability allowlist must have a fresh sidecar. | Durability is "everywhere" literally |
| E9 | **Continuous decode-drill**: every CI run picks a random committed sidecar, deletes 30% of its repair symbols, runs `fnx-durability decode-drill`, emits a decode proof under `artifacts/conformance/latest/decode_proofs/`. SPEC §19 says decode proofs must be emitted per-recovery-event; today this is theoretical. | Recovery exercised, not declared |
| E10 | **Adversarial decode-drill**: pre-corrupt 1 packet, 5 packets, 50% of packets, all packets — assert recovery succeeds up to the published RaptorQ overhead ratio and *fails closed* beyond. The failure case is as important as the success case. | Durability bounds are proven, not assumed |
| E11 | **Memory regression profile** (memory budget was doubled in commit 742c48e — needs justification or restoration): per-fixture peak-RSS measurement via `dhat`/`heaptrack`, committed under `artifacts/perf/memory/<fixture>/heaptrack.html`. Gate: peak-RSS regression ≤ +10% per SPEC §17. | Memory budget honest |
| E12 | **Tail-stability gate** (p99 budget was tripled — same): per-family p99 measured 30 times in CI to expose noise; gate fails if p99 distribution shifts > +10% per SPEC §17. | p99 stability provable |

### Track F — Long-tail polish, NX-REPLACE residue, doc freshness

| Bead | Title | Outcome |
|---|---|---|
| F1 | Final NX-REPLACE wave: eliminate the remaining 15 `_to_nx` and 4 `_networkx_compat_graph` references in `python/franken_networkx/__init__.py`. Audit each: native impl OR explicit `# DELEGATED_TO_NETWORKX` marker excluded from parity claims. | `_to_nx` count → 0 |
| F2 | Auto-discovery for backend dispatch: replace `backend.py:_SUPPORTED_ALGORITHMS` hard-coded dict with a generated registry sourced from a single Rust manifest. Adding a new Rust algorithm auto-extends backend coverage. | Zero hand maintenance for backend dispatch |
| F3 | Generated coverage matrix: a script that walks `__init__.py`, classifies each export as `RUST_NATIVE` / `PY_WRAPPER` / `NX_DELEGATED`, and writes `docs/coverage.md`. CI gate: zero unclassified. | Honest, machine-checked parity claims |
| F4 | Triage 54 currently-skipped Python tests: open a bead per skip reason cluster, plan to land each. | Skip count drops monotonically |
| F5 | Update FEATURE_PARITY.md to reflect actual reality: most rows still `in_progress` is honest; replace marketing language ("100% NX top-level function parity") with the generated coverage matrix link from F3. | Doc matches code |
| F6 | Update README "Current State" with a current snapshot generated from `git log` + `br list --status=closed --json` (most recent 20 closures). Replace stale "Next Steps" with the Track A-E plan. | README reflects 2026 reality |
| F7 | Refresh `CHANGELOG.md` from commit history since 2026-03-22 (the last entry); make changelog regeneration part of release flow | Changelog current |

---

### Track G — Crown-jewel multipliers (round 3 ambition: the things competing NetworkX ports would never reach for)

**Ambition note (round 3):** Tracks A-F close the gap between code and spec. Track G is what makes the project *leapfrog* every other NetworkX port. The README boasts four methodological disciplines: alien-artifact-coding, extreme-software-optimization, RaptorQ-everywhere, and frankenlibc compatibility-security thinking. Tracks A-F operationalize the latter two. Track G operationalizes the first two by reaching into actually-hard math from the last 60 years that nobody else in this space uses.

| Bead | Title | Outcome |
|---|---|---|
| G1 | **Conformal-prediction performance bands**. Instead of asserting `p95 ≤ 420 ms`, fit a *split-conformal* regressor on (graph_features → runtime) using historical benchmark runs; emit a per-PR prediction band `[lo, hi]` with calibrated coverage (e.g. 95%). A regression is a runtime falling outside the upper band. This converts perf gating from frequentist threshold to distribution-free prediction with finite-sample coverage guarantees. *No NetworkX port does this.* | Calibrated, distribution-free perf gating |
| G2 | **Bayesian rare-event estimation** for tail latency. p99/p99.9 estimation by hand from 30 samples is statistically nonsense. Use Generalized Pareto tail modeling (Peaks-Over-Threshold) and emit posterior distributions for p99/p99.9 with credible intervals. Gate on the lower CI bound of the budget, not the point estimate. | Tail SLOs are statistically honest |
| G3 | **Witness-hash → SAT counter-example mining** for CGSE. When the property suite finds two graphs where fnx and NX disagree on tie-break order, encode the disagreement as a SAT instance and use a minimizer (e.g. delta-debugging) to find the smallest divergence-inducing graph. Auto-attach to the beads issue created by B7. | Drift bugs come with minimal repros |
| G4 | **Graph-isomorphism-aware regression deduplication**. The regression corpus (B8) will accumulate near-duplicate fixtures over time. Use NX's own `is_isomorphic` (or fnx's, faster) to canonicalize and dedupe. Each unique graph stays once with all its provenance bead-IDs attached. | Regression corpus stays small and signal-dense |
| G5 | **Information-theoretic fuzz prioritization**. Rather than random fuzzing, weight inputs by the *KL divergence* of their resulting code-coverage histogram from the historical mean — fuzz the inputs that reveal the most novel paths first. Implementable as a libFuzzer custom mutator. | Fuzz hours buy more bugs |
| G6 | **Algebraic effect tracking for parser modes**. Use the type system to encode parser side-effects (warning emissions, mode transitions, recovery actions) as an effect row, so any parser change that adds/removes an effect is a compile-time signature change. This is the type-level version of the decision ledger. | Mode-divergence regressions become compile errors |
| G7 | **Persistent-homology graph fingerprinting** for fixture clustering. Compute a 0/1-dim persistent homology signature for each conformance fixture and use it to (a) detect when the corpus is over-sampling one topological class and (b) auto-suggest gaps. This addresses the SPEC §17 "adversarial classes" mandate by *measuring* class diversity rather than asserting it. | Adversarial coverage measurable, not asserted |
| G8 | **Compressed-sensing replay logs**. The decision ledger (D7) and witness ledger (C3) are append-only and grow forever. Use a count-min sketch + reservoir sampling to keep a fixed-size summary alongside the full log; CI uses the summary for fast checks, full log for deep audit. RaptorQ-sidecared per SPEC §9. | Ledgers stay bounded without losing audit |
| G9 | **Optimal-transport fixture diversity**. Use Wasserstein distance on graph spectra to ensure the fixture corpus is *maximally diverse* — when adding a new fixture, prefer ones that increase corpus Wasserstein diameter. This is a principled answer to "how do we know we have enough fixtures?" | Corpus diversity becomes optimizable |
| G10 | **Differentiable graph layout for benchmark visualization**. The conformance dashboard (B11) becomes a force-directed map of fixtures colored by drift status, layout via differentiable optimization, so adjacent fixtures share failure modes — humans see clusters at a glance. | Dashboards reveal structure |

**Track G is optional.** Each item is justified independently and would each be a credible publishable artifact. Implementing G1+G2 alone (conformal perf bands + Bayesian tail SLOs) would put the project's perf doctrine ahead of every NetworkX-replacement project that exists. Implementing G3+G7 would make CGSE a research contribution rather than just engineering.

---

## 3. Tier-1 critical path (the 6 things that matter most)

If only 6 bullets land, do these:

1. **A1 + A2 + A3** — Repo hygiene reset. Without this every other agent session adds more debris.
2. **B2 + B3 + B4** — Conformance freshness. Without this we cannot truthfully claim Gate A passes.
3. **C1** — CGSE decision point. Either implement (C2-C6) or retract (rewrite README + SPEC §0). The half-built version is the worst outcome.
4. **D1 + D2 + D3 + D4** — Strict/Hardened wiring (or retraction). Same logic.
5. **E1 + E3** — SLO restoration + perf gate in CI. Without this, "performance-competitive" is not provable.
6. **F1 + F3** — Final `_to_nx` elimination + machine-checked coverage matrix. Without this, parity claims are not auditable.

---

## 3.1 Refinement notes (Phase 5 round 1)

After the ambition rounds I walked every bead checking sense / dependency correctness / test coverage. Added the following:

- **Track A6 was vague.** Restated: "`br doctor` reports `gitignore.beads_inner` and `db.sidecars` warnings; A6 must (a) remove the `.beads/` line from root `.gitignore`, (b) verify SHM/WAL co-exist correctly, (c) re-run `br doctor` until 100% OK." The current `br list` returning 0 while JSONL has 217 closed records is the consequence of these warnings; A6 must include a regression test (a smoke that creates an issue, lists it, closes it, lists again).
- **B5 had an ambiguous direction.** Made it explicit: pytest is the active oracle, Rust harness becomes a thin driver. Without this, B2-B4 are running an empty harness.
- **C2 needs a *non-goal* clause**: CGSE policies are not pluggable by users in V1 — the type-level enumeration is closed. User-pluggable policies are V2. Otherwise C9 (public API) explodes the V1 scope.
- **D4 Bayesian admission controller** assumes a prior. The bead must specify how the prior is initialized (recommend: empirical, from D5 loss matrix calibration on the adversarial corpus).
- **E1 SLO restoration** must specify *which* commit's SLO values to restore. The pre-742c48e SLOs are in the git history at `git show 742c48e^:artifacts/perf/slo_thresholds.json`.
- **B6 metamorphic testing** needs a non-trivial example list per family — without it the bead becomes "write some metamorphic tests" which is the kind of vague that gets stalled. Added 4 example relations per family in the bead body (when expanded into beads tracker).
- **G2 GPD tail modeling** needs a sample-size minimum (at least 1000 measurements before fitting); add a precondition bead that ensures the perf workload runs long enough.
- **Cross-track dependencies** that were implicit:
  - C5 (CGSE adversarial corpus) **blocks** G3 (SAT counter-example mining).
  - D5 (loss matrix) **blocks** D4 (Bayesian admission), not after it.
  - B8 (regression corpus) **blocks** G4 (isomorphism dedup).
  - E2 (workloads) **blocks** E3 (profile-and-prove loop) — can't profile without workloads.
  - G1 (conformal bands) **requires** at least 30 historical benchmark runs — schedule it after E2+E4 have collected data.
- **Test-companion completeness**: Tracks C, D, G all need pytest-level integration tests in addition to Rust unit tests, since the Python parity suite is the active oracle.
- **AGENTS.md compliance**: Track A1 deletions require explicit user permission per Rule 1; the bead body must include the proposed file list and a checkbox for user sign-off, not just "delete the debris."

## 4. Test scaffolding (every implementation bead needs companion test beads)

Every bead in the tracks above must declare:

1. **Unit test** in the relevant crate's `#[cfg(test)]` block.
2. **Integration test** in the workspace `tests/` directory (for cross-crate work).
3. **Conformance fixture** in `crates/fnx-conformance/fixtures/` (for any output-affecting change).
4. **Python parity test** in `tests/python/` (for any user-visible API change).
5. **Structured log assertion** (for any decision-emitting code).
6. **RaptorQ envelope assertion** (for any persistent artifact).

The "DO NOT OVERSIMPLIFY" / "DO NOT LOSE FEATURES" frozen template instruction applies — these tests must be written before or alongside the implementation, not retroactively.

---

## 4.1 Refinement notes (Phase 5 round 2)

Second sweep focused on sequencing, risk, and rollback. New findings:

- **Sequencing risk in Track A.** A3 (promote/delete root tests) can hide bugs the root tests are catching that the formal `tests/python/` doesn't. Mitigation: run *both* root and formal tests one final time before deleting; diff results; any test passing only in root must be promoted, not deleted. Add A3.1: "Root-test salvage diff."
- **Track B freshness gate (B4) interacts badly with branch development.** If `crates/fnx-algorithms/` changes on a feature branch, the freshness gate forces a full conformance regen *on the branch* before merge. This is correct but slow. Mitigation: B4 should accept a `[skip-freshness]` PR label paired with a follow-up bead auto-created on merge to main. Add B4.1.
- **CGSE compile-time policy parameters (C2) may inflate compile times.** Const generics over algorithm families can cause monomorphization explosion. Mitigation: measure compile time delta; if it exceeds 20%, switch to runtime dispatch with a `#[cfg(test)]` compile-time check. Add C2.1.
- **Track D loss matrix calibration (D5) is empirically thin.** With only ~24 strict + 24 hardened fixtures, calibrating a per-parser-per-attack-class loss matrix produces noisy estimates. Mitigation: D5 must include a Bayesian shrinkage prior (e.g. hierarchical model with parser as group, attack class as level) to handle small samples honestly. Add D5.1.
- **Track E flamegraph commits will balloon the repo.** SVG flamegraphs are 1-5 MB each; 8 of them × every regression sweep × git history = repo bloat. Mitigation: store flamegraphs as compressed `.svg.gz` under `artifacts/perf/proof/<bead>/`, gitignore the uncompressed form, and emit them via `rch` rather than locally. Add E3.1.
- **Track G is not on the critical path** but G1 and G2 have a *prerequisite* dependency on E2+E4 having collected ≥30 historical benchmark runs. Without that data, conformal regression and Bayesian tail estimation are unfittable. Add G0: "Wait for ≥30 perf runs in `artifacts/perf/history/` before starting G1+G2."
- **Rollback plan missing.** Every Track C/D bead changes algorithm output ordering or parser behavior. If a change is wrong, rollback today means `git revert` of a single commit — but the conformance reports and witnesses generated against the bad commit will live in `artifacts/conformance/latest/`. Add a Track-level rollback bead per track: "Tag pre-track conformance bundle as `last-known-good`, publish revert procedure, document one-command rollback."
- **Risk note matrix (per AGENTS.md "Required evidence for substantive changes")**: every track in §2 needs a `risk_note.md` filed alongside the work. Following the template at `artifacts/phase2c/templates/risk_note.md`. New cross-cutting bead: H1 "Author risk_note.md per track per the project's existing template."
- **Differential test gap**: the Python pytest suite tests fnx vs NX on the *same* graph. It does *not* test that fnx, fnx-after-edit, and fnx-after-roundtrip-through-each-format produce identical results. Add a new B-track bead: B12 "Round-trip identity tests for every parser × every graph type."
- **NX backend mode coverage gap**: I asserted "narrow dispatch dict" for V2. Actual measurement: count `_SUPPORTED_ALGORITHMS` entries vs total nx top-level functions. Add a new F-track bead: F8 "Backend dispatch coverage measurement and gap report."
- **The `_to_nx` count of 15 may include false positives** (string literals, comments). Verify with `ast-grep` per AGENTS.md guidance, not raw `grep -c`. Add F1.1: "Use ast-grep to confirm true call-site count before declaring F1 done."
- **Documentation freshness gate** (F5/F6/F7) should not be a one-time bead but a recurring CI check. Add a new F bead: F9 "CI gate that fails if README.md / FEATURE_PARITY.md / CHANGELOG.md is older than HEAD~50 commits."
- **Beads dependency loops**: B7 (differential fuzzing creates beads on disagreement) → can create beads that block B7's own CI run. Mitigation: differential fuzz beads are auto-tagged `quarantine`, and B7's gate ignores `quarantine`-tagged beads on first creation but blocks on second occurrence.
- **AGENTS.md "Backwards Compatibility: we don't care, no tech debt"** clause means many of the "decision/retraction" beads (C1, D1, E1) should default to *implement*, not *retract*. Update the §3 critical path to make this explicit.

## 5. Acceptance criteria for the bridge as a whole

- All 21 gaps in §1 either closed or formally retracted from spec.
- `git status` clean on `main`; `br doctor` reports no `WARN` entries; `cargo fmt --check`, `cargo clippy --workspace --all-targets -- -D warnings`, `cargo test --workspace`, `pytest tests/python/` all green.
- `artifacts/conformance/latest/` reports all dated within 24 hours of HEAD; every report has a RaptorQ sidecar with `scrub.status: ok`.
- `.github/workflows/{conformance,perf,fuzz}.yml` exist and run on every PR.
- `docs/coverage.md` shows zero unclassified exports.
- README "Current State" / "Next Steps" / FEATURE_PARITY.md / CHANGELOG.md reflect HEAD.
- Beads tracker: every gap from §1 has either a closed bead or an open bead with full context.

---

## 5.1 Refinement notes (Phase 5 round 3) — bead IDs, priorities, dependency graph

Final structural pass before Phase 3a (bead generation). Assigning provisional IDs, priorities (P0=critical / P1=high / P2=medium / P3=low), and explicit `blocks`/`blocked_by` relations.

### Priority assignment

| Tier | Beads | Total |
|---|---|---|
| **P0 (critical, blocks release-readiness)** | A1, A2, A4, B1, B2, B3, B4, B5, C1, C2, C3, C4, D1, D2, D3, D4, E1, E4, E5, F1, F3 | 21 |
| **P1 (high, blocks the next vertical slice)** | A3, A5, A6, B6, B7, B8, B9, B10, C5, C6, C7, D5, D6, D7, E2, E3, E6, E7, E8, E9, F2, F4, F5, F6, B11, B12, F8, F9, H1 | 29 |
| **P2 (medium, polish & expansion)** | C8, C9, D8, D9, E10, E11, E12, F7 | 8 |
| **P3 (research multipliers, optional)** | G0, G1, G2, G3, G4, G5, G6, G7, G8, G9, G10 | 11 |

**Total: 69 beads** across 7 tracks. Of these, 21 are critical-path P0s without which the SPEC's V1 acceptance gates cannot honestly pass.

### Dependency graph (only the load-bearing edges)

```
A1 (cleanup) ── blocks ──> A4 (commit in-flight tests)
A2 (gitignore) ── blocks ──> A1 (so cleanup is reproducible)
A6 (br doctor) ── blocks ──> all bead-creation work below
B1 (decide source) ── blocks ──> B2 ──> B3 ──> B4 ──> B5
B5 ── blocks ──> B6, B10, B11
B7 (diff fuzz) ── blocks ──> G3 (SAT mining)
B8 (regression corpus) ── blocks ──> G4 (iso dedup)
C1 (decision) ── blocks ──> C2 ──> C3 ──> C4 ──> C5 ──> C6 ──> C7 ──> C8 ──> C9
C5 ── blocks ──> G3
D1 (decision) ── blocks ──> D2 ──> D3, D4
D5 (loss matrix) ── blocks ──> D4 (Bayesian admission)
D7 (decision ledger) ── blocks ──> D8 (drift feedback)
E1 (restore SLOs) ── blocks ──> E3 ──> E4
E2 (workloads) ── blocks ──> E3, G0
E4 (CI gate) ── blocks ──> G0 (≥30 runs needed)
E6 (parser fuzz) ── blocks ──> E7 (algo fuzz)
E8 (RaptorQ coverage) ── blocks ──> E9 (decode drill) ──> E10 (adversarial drill)
F1 (eliminate _to_nx) ── blocks ──> F3 (coverage matrix)
F3 ── blocks ──> F5 (FEATURE_PARITY rewrite)
G0 (collect 30 runs) ── blocks ──> G1, G2
```

### Critical-path linearization

The 21 P0 beads can be sequenced into 4 waves with maximum parallelism:

**Wave 1 (process & decisions, parallel):**
- A1 + A2 + A4 (hygiene, requires user permission)
- A6 (br doctor sync)
- B1 (decide conformance source)
- C1 (decide CGSE implement vs retract)
- D1 (decide modes implement vs retract)
- E1 (decide SLO restore vs documented downgrade)

**Wave 2 (foundation, depends on Wave 1):**
- B2 + B3 + B4 + B5 (conformance regen + freshness gate)
- C2 + C3 (CGSE policy + witness types)
- D2 (mode dispatch type)
- E4 (G1→G8 CI gate wiring) + E5 (perf gate wiring)
- F1 (final `_to_nx` wave)

**Wave 3 (algorithm wiring, depends on Wave 2):**
- C4 (12 algorithms wired through CGSE)
- D3 + D4 (strict + hardened parser fixtures)
- F3 (machine-checked coverage matrix)

**Wave 4 (ready for release):**
- All P1 beads in priority order
- P2/P3 as capacity allows

### Acceptance evidence per bead (the rule)

Every bead's `acceptance_evidence` field must specify, before the bead can be closed:

1. **Code change reference**: commit hash + crate file path + line range.
2. **Test reference**: pytest node ID OR cargo test name.
3. **Conformance fixture reference**: fixture path + report hash (if output-affecting).
4. **Performance evidence**: benchmark percentile artifact path (if perf-touching).
5. **Decision-ledger record**: ledger entry hash (if mode/policy-touching).
6. **Risk note reference**: `risk_note.md` path (per AGENTS.md required-evidence rule).
7. **RaptorQ envelope reference**: sidecar path + scrub status (if artifact-emitting).

A bead missing any of these for its category cannot be closed. This is the spec's "required evidence for substantive changes" made operational.

### Bead naming convention

Provisional IDs in this plan are local (`A1`, `B2`, etc). When ingested into beads tracker via `br create -f`, they will get `franken_networkx-XXXX` IDs auto-assigned. The local IDs map into bead `description` headers as `[A1]`, `[B2]`, etc., and into commit messages, so cross-references survive.

## 5.2 Refinement notes (Phase 5 round 4)

Final pass. New findings (most are small but several are load-bearing):

- **Missing Track: H — Cross-cutting governance.** Risk notes (H1) were added in round 2 but not given a track of their own. Promoting H to a real track:
  - **H1** Risk notes per track per `artifacts/phase2c/templates/risk_note.md`.
  - **H2** Threat-model notes per major subsystem (SPEC §5 mandate, currently missing — only `crates/fnx-runtime/` and `crates/fnx-readwrite/` are obvious candidates).
  - **H3** RFC process for any change touching strict/hardened mode boundaries — proposed in `docs/rfc/`, voted on by tagging the bead with `rfc-required`.
  - **H4** Quarterly compliance audit: a recurring bead that walks every claim in the README + SPEC and reverifies it. Schedules itself via `bv --robot-forecast`.
  - **H5** "Last-known-good" snapshot tagging: every successful G1→G8 run tags the commit `lkg-YYYY-MM-DD-HHMM` so rollback is one command.
- **The conformance dashboard (B11) is read-only.** Add B11.1: a *contributor view* that shows, per-PR, which fixtures the PR's HEAD changes vs main, with diff highlighting. Without this, `B11` is for spectators not contributors.
- **No data on how many tests are skipped *and why*.** F4 is "triage 54 skipped tests" but doesn't specify the format. Add F4.1: each skip must have a `reason` literal (currently many are bare `pytest.skip()`); a CI gate fails on bare skips. This is the test-discipline analog of E1's perf-discipline.
- **The `tests/python/conftest.py` has hypothesis fixtures.** I deliberately excluded `test_hypothesis.py` from the smoke run for time. Add B6.1: "Run hypothesis suite in CI nightly with a 10-minute budget; commit the database under `.hypothesis/`."
- **MultiGraph is the only `parity_green` family** (FEATURE_PARITY L29). The other 13 families need a clear definition of "what does parity_green even *mean* operationally". Add F5.1: "Define parity_green operational criteria — recommend: zero strict-mode drift across the full Tier B corpus + zero open `*-parity-gap` beads + freshness < 24h."
- **`fnx-views` cache invalidation under concurrent reads** (B10) needs a thread-safety story. Today the GIL likely makes this moot in Python, but the Rust crate is multi-threaded internally. Add B10.1: "Loom test for view cache under concurrent mutator/reader."
- **Performance memory budget** (E11) talks about peak RSS but the SPEC's actual term is "memory footprint" — which can include memory the allocator returned to the OS or not. Specify the metric: `dhat`'s `t-gmax` or `heaptrack`'s "peak heap"; document which one and why; gate on it.
- **The `errors.json` 572KB file** in repo root: before deletion, *parse* it to extract any unique signal (compiler errors, test failures) that should become a beads issue. Add A1.0: "Triage `errors.json` and `*ubs*.txt` for unrecorded bugs before deletion."
- **The `_fnx.abi3.so` 81 MB binary** in `python/franken_networkx/` is committed (or at least tracked by `ls -l`). Verify whether it's gitignored; if not, it absolutely should be. Add A2.1: "Audit committed binary blobs."
- **The `dist/` directory** (Maturin wheel output) needs gitignore. Same for `fuzz/target/`, `.benchmarks/`, `venv/`, `.venv/` — A2 listed them but didn't separate "needs git rm --cached" from "just needs gitignore."
- **AGENTS.md "RaptorQ-Everywhere Contract"** lists 5 categories of artifacts requiring sidecars. I covered all 5 in E8 but didn't enumerate them in the bead body. Add explicit checklist:
  - [ ] Conformance fixture bundles
  - [ ] Benchmark baseline bundles
  - [ ] Migration manifests
  - [ ] Reproducibility ledgers
  - [ ] Long-lived state snapshots
- **`UPGRADE_LOG.md` exists but isn't part of the freshness story.** Either include it in F9's freshness gate or formally retire it.
- **CHANGELOG entries** (F7) need a *generator script* not a manual rewrite, otherwise it'll go stale again. Add F7.1: "`scripts/regenerate_changelog.py` from `git log` + closed beads."
- **Cross-platform**: nothing in the plan addresses Windows/macOS support. The README implies cross-platform wheels via abi3-py310. Add a new bead: F10 "Cross-platform CI matrix (Linux/macOS/Windows × Python 3.10/3.11/3.12/3.13)."
- **Beads dependency declarations**: `br create --deps` syntax wants `type:id`. Each bead in §3 critical-path linearization needs to be created with explicit `--deps` flags during Phase 3a, otherwise the dependency graph is metadata-only.
- **Acceptance evidence rule** (§5.1) doesn't say where the evidence record is stored. Specify: in the bead's `description` body, in a YAML front-matter block parseable by `bv --robot-history`.
- **Track G has 11 beads but no critical-path role.** Reorder §3 to put Track G under "Phase 6: leapfrog ambition" and explicitly mark it as deferrable until after V1 ships.
- **The "round 3 ambition" Track G items reference math** (conformal prediction, GPD tail modeling, persistent homology) but don't cite a *Rust crate* that implements them. Each G bead needs a "candidate dependency" line: e.g. G1 → `conformal-prediction` crate (or build atop `linfa`); G2 → `evd` (extreme value distribution) or hand-rolled GPD; G7 → `phat-rs` (none exists, would need to build). Add a precondition bead per G item: "evaluate or stub the math dependency before scheduling."

## 5.3 Refinement notes (Phase 5 round 5) — final convergence sweep

After round 4, walked the plan again checking for new gaps. Findings:

- **Plan is now ~70 beads, organized in 8 tracks (A-G + H), with 21 P0s sequenced into 4 waves.** Round 4 was the largest delta; round 5 finds only minor things.
- **One genuine gap remaining**: nothing in the plan addresses **error message quality**. NetworkX has carefully-tuned error messages; FrankenNetworkX needs parity here too or users will perceive it as "lower quality" even when correct. Add bead F11: "Error message parity audit — every `raise` in `fnx-algorithms` and `fnx-readwrite` matches NX's wording within Levenshtein-3."
- **`tests/python/test_error_messages.py` exists** (per AGENTS.md L102) but isn't currently exercised in my smoke. Add B6.2: include it in the parity gate.
- **Examples directory**: `examples/basic_usage.py`, `backend_mode.py`, `social_network.py`, `benchmark_comparison.py` are listed in README L93-96. Are they runnable on current code? Add F12: "CI gate runs every `examples/*.py` end-to-end on every PR."
- **No bead for `pyproject.toml` cleanup.** With dist/ and abi3 binary committed, the build manifest probably has cruft too. Add A7: "pyproject.toml audit."
- **No bead for license / contribution / security policy files** (LICENSE exists; SECURITY.md, CONTRIBUTING.md, CODE_OF_CONDUCT.md may not). Add F13: "OSS hygiene files."

Round 5 found 5 small additions. I will run **one more refinement (round 6)** since the rule is "stop only when a round finds nothing." If round 6 finds nothing, the plan is converged.

## 5.4 Refinement notes (Phase 5 round 6) — convergence check

Final walk. Looking specifically for: missing tracks, broken dependencies, unstated invariants, vague success criteria, dependencies on deprecated tools.

- **Plan now lists 8 tracks, ~75 beads, full dependency graph, priority assignment, acceptance evidence rule, rollback story, governance track.** Walking each track end-to-end finds no new gaps.
- **The plan is internally referentially consistent** — every cross-reference (e.g. "B7 blocks G3") matches the bead it points to.
- **Every P0 has at least one P1 follow-up** that strengthens it; no P0 is a dead-end.
- **Every track has a measurable acceptance criterion** (§5 acceptance criteria + each bead's evidence rule).
- **The plan correctly distinguishes** between "implement" (default per AGENTS.md backwards-compat clause) and "retract" (the honest fallback) for the three strategic decisions C1/D1/E1.
- **Round 6 finds nothing new.** Plan is converged.

**Phase 5 → done. Ready for Phase 3a (bead generation).**

## 6. Open questions for the user

1. **Repo cleanup blast radius.** AGENTS.md Rule 1 forbids deletion without explicit permission. Track A1 needs blanket permission for the categories listed, OR a per-file approval. Recommend: blanket permission for `fix_*.py`, `find_*.py`, `patch_*.py`, `*.bak`, `chunk*.txt`, `*ubs*.txt`, `errors.json`, `clippy_output.txt`, `rust-bug-scan.txt`, `print_edges.rs`, `run_manual_test_msd.rs`, `test_d_rust` (10 MB binary), and per-file approval for the ~75 root `test_*.py`/`test_*.rs`.
2. **CGSE implement vs. retract** (C1) — this is a strategic call.
3. **Strict/Hardened implement vs. retract** (D1) — same.
4. **SLO restoration vs. downgrade rationale** (E1) — same.
5. **Conformance source of truth** (B1) — Rust harness or Python pytest? Recommend Python (it actually runs and passes), with the Rust harness retired.
