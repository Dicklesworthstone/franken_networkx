# Reality Check Bridge — 2026-04-08 bead bulk import

> Generated from REALITY_CHECK_BRIDGE_PLAN_2026-04-08.md after Phase 1 reality check, 3 ambition rounds, and 6 plan-space refinement rounds.
> Each bead is self-contained: future agents must not need to read the bridge plan or original session to understand goal, context, evidence, and acceptance criteria. Every bead embeds the relevant SPEC/AGENTS/README references, the *why*, and the *how-to-prove-done*.

## [A1] Repo root cleanup: stage agent debris for deletion or relocation

**Track:** A — Process & hygiene reset.
**Priority:** P0.
**Type:** task.

**Why this exists.** AGENTS.md L137-152 is unambiguous: "NEVER run a script that processes/changes code files in this repo. Brittle regex-based transformations create far more problems than they solve." It also says "NEVER create variations like mainV2.rs / main_improved.rs." The repo root currently contains 24+ files violating both rules: `fix_allow_threads.py`, `fix_allow_threads2.py`, `fix_allow_threads3.py`, `fix_allow_threads_final.py` (sequential failed agent attempts), `fix_algorithms.py`, `fix_dijkstra.py`, `fix_eulerize.py`, `fix_matrix.py`, `fix_missing_allow_threads.py`, `fix_py.py`, `fix_ruff.py`, `fix_ruff2.py`, `fix_shortest_paths.py`, `fix_undirected.py`, `fix_gbc.rs`, `find_all_funcs.py`, `find_clones.py`, `find_funcs.py`, `find_missing.py`, `find_missing_allow_threads.py`, `patch_matrix.py`. Plus ~75 root-level `test_*.py`/`test_*.rs` ad-hoc scripts (separate from `tests/python/`), `crates/fnx-python/src/algorithms.rs.bak`, `python/franken_networkx/chunk{,1,2,3}.txt`, ~27 MB of UBS/clippy/bug-scan dumps (`current_ubs_report.txt`, `full_ubs_report.txt`, `rust-bug-scan.txt`, `ubs_out.txt`), `errors.json` 572 KB, `print_edges.rs`, `run_manual_test_msd.rs`, and a 10 MB `test_d_rust` binary. None gitignored. None referenced from build files. The pattern is the smoking-gun fingerprint of repeated agent sessions debugging by writing throwaway scripts — the exact failure AGENTS.md was meant to prevent. Without this cleanup, every future agent inherits the debris and adds more.

**Reasoning / context for future-self.** The `fix_allow_threads` 1→2→3→final sequence is especially diagnostic: it represents 3 failed iterations of a forbidden mass-edit workflow before someone gave up. The `chunk*.txt` files inside the package directory suggest an LLM split a generator file during a refactor and never cleaned up. The `errors.json` is raw cargo/clippy output that should have been read once and discarded. None of this is "in-progress work that other agents will pick up." It's tombstones.

**Pre-deletion triage.** Per AGENTS.md Rule 1 ("NEVER allowed to delete a file without express permission"), this bead requires explicit user sign-off on the file list. Before deletion: parse `errors.json` and `*ubs*.txt` for any unique signal (compiler errors, real bugs) that should become its own bead — that's task A1.0 below. After triage and approval, files in `scripts/dev/` (if reusable) or deletion list (if not).

**File list for user approval (delete unless marked KEEP):**
- DELETE: all `fix_*.py` (15 files), all `find_*.py` (5 files), all `patch_*.py` (1 file), `print_edges.rs`, `run_manual_test_msd.rs`, `test_d_rust` (10 MB binary), `test_d_rust.rs`, `crates/fnx-python/src/algorithms.rs.bak`, `python/franken_networkx/chunk*.txt` (4 files), `errors.json`, `clippy_output.txt`, `current_ubs_report.txt`, `full_ubs_report.txt`, `rust-bug-scan.txt`, `ubs_out.txt`, `ubs_report.txt`, `debug_extract.patch`, `get_mismatches.patch`, `trace.patch`, `fix_unreachables.py`.
- TRIAGE then DELETE: ~75 root-level `test_*.py` / `test_*.rs` (covered separately by A3 — root-test salvage diff).

**Acceptance evidence.**
1. User approval recorded in bead body as a comment.
2. `git rm` commit hash for the deletion.
3. `git status` clean for the affected paths.
4. `ls /data/projects/franken_networkx | wc -l` < 30 (currently ~158).
5. Risk note `artifacts/risk_notes/A1_repo_cleanup_risk_note.md` per `artifacts/phase2c/templates/risk_note.md`.

**Blocks:** A4 (cannot commit in-flight tests cleanly while debris is staged).
**Blocked by:** A1.0 (errors.json triage), A2 (.gitignore audit must precede deletion so re-creation is blocked).

priority: 0
type: task

## [A1.0] Triage errors.json and *ubs*.txt for unrecorded bugs before deletion

**Track:** A.
**Priority:** P0.
**Type:** task.

**Why.** The 27 MB of static-analysis dumps may contain unique findings (UBS warnings, clippy lints, compiler errors) that were never converted into beads or fixes. Deleting the files without triage loses that signal forever. AGENTS.md rule on root-cause-not-shortcut applies.

**Method.** Run `jq` over `errors.json`; for each unique error category, check whether the underlying issue still exists in the current code (`cargo check`, `cargo clippy --workspace --all-targets -- -D warnings`); for any that does, file a P1 bead under the appropriate track. Same approach for `current_ubs_report.txt` etc.

**Acceptance evidence.** A summary report under `artifacts/triage/2026-04-08_root_dump_triage.md` listing categories, current-status check, and any new bead IDs created. Approved by user before A1 proceeds to deletion.

**Blocks:** A1.

priority: 0
type: task

## [A2] .gitignore audit and re-baseline

**Track:** A. **Priority:** P0. **Type:** task.

**Why.** Several artifact directories and binary blobs are not gitignored: `target/`, `.venv/`, `venv/`, `dist/`, `fuzz/target/`, `.benchmarks/`, `.hypothesis/`, `.ruff_cache/`, `.pytest_cache/`, `python/franken_networkx/_fnx.abi3.so` (81 MB), `python/franken_networkx/__pycache__/`, plus the categories from A1 (`*.bak`, `*ubs*.txt`, `errors.json`, `clippy_output.txt`, `rust-bug-scan.txt`). Without these entries, every cleanup re-grows the debris.

**Method.** Add explicit per-pattern entries (not blanket wildcards). Verify each path is currently in the working tree (`ls -la`). For any committed binary blob (`_fnx.abi3.so` is the prime suspect), `git rm --cached` then commit gitignore in same atomic commit. Run `git status` after to confirm working tree clean.

**Acceptance evidence.** Updated `.gitignore` committed. `git status` clean. `git ls-files | xargs -I{} stat --printf='%s %n\n' {} | sort -rn | head -20` shows no files > 5 MB unless explicitly justified.

**Blocks:** A1, A4.

priority: 0
type: task

## [A2.1] Audit committed binary blobs

**Track:** A. **Priority:** P1. **Type:** task.

**Why.** `python/franken_networkx/_fnx.abi3.so` is 81 MB and may be tracked. `test_d_rust` is a 10 MB committed binary. Wheel artifacts under `dist/` may also be tracked.

**Method.** `git ls-files | xargs -I{} test -f {} && file {}` to find all binaries; `git ls-files --cached | xargs du -k 2>/dev/null | sort -rn | head -30`. Untrack any binary > 1 MB unless explicitly justified.

**Acceptance.** Repo size before/after recorded; commit hash; explanation per file.

priority: 1
type: task

## [A3] Promote or delete the ~75 ad-hoc root-level test scripts

**Track:** A. **Priority:** P1. **Type:** task.

**Why.** ~75 files matching `test_*.py` or `test_*.rs` exist at the repo root, separate from the canonical `tests/python/`. Pytest does not collect them (they're outside the test rootdir). They're orphaned: not run, not maintained, not gitignored. A subset may exercise unique edge cases that the canonical suite doesn't cover.

**Method (A3.1 — root-test salvage diff).**
1. Run every root `test_*.py` once (skip on first error per file) and capture output.
2. Run the canonical `tests/python/` suite and capture coverage.
3. For any root test that exercises a function NOT touched by canonical coverage: promote into `tests/python/` under an appropriate `test_*.py` file, refactor to standard pytest style.
4. For any root test that duplicates canonical coverage: delete (with permission per AGENTS.md Rule 1).
5. For any root test that fails: file a P1 bead in the appropriate algorithm-family track with the failure as a fixture, then delete the root file.

**Acceptance evidence.** Coverage report before/after under `artifacts/triage/2026-04-08_root_test_salvage.md`. Each root `test_*.py` either deleted, promoted (with new pytest path), or filed as a bead. Final root-level `test_*.py` count = 0.

**Blocked by:** A1, A2.

priority: 1
type: task

## [A4] Commit or revert the 10 in-flight test files

**Track:** A. **Priority:** P0. **Type:** task.

**Why.** `git status` shows 10 modified-but-uncommitted test files: `tests/python/test_io_conversion_parity.py`, `test_k_edge_augmentation_parity.py`, `test_native_replacements_parity.py`, `test_parity_comprehensive.py`, `test_rust_wiring_parity.py`, `test_sort_neighbors_parity.py`, `test_trophic_parity.py`, `test_untested_coverage.py`, `test_view_default_parity.py`, plus `python/franken_networkx/__init__.py`. These are in-flight from the recent NX-REPLACE wave (commits 69f8cc5, c69eb98, ecb229e) and need to be either landed or reverted before any further track work. Leaving them dirty causes every other bead's diff to be impossible to review cleanly.

**Method.** Run `pytest tests/python/test_*_parity.py` against current state to confirm they pass. If yes: commit as a "land in-flight NX-REPLACE parity tests" commit. If no: bisect against the relevant NX-REPLACE bead, fix, then commit. Only revert as last resort.

**Acceptance.** `git status` shows zero modified files in `tests/python/`. Commit hash recorded.

**Blocked by:** A1, A2.

priority: 0
type: task

## [A5] Resolve crates/fnx-python/src/algorithms.rs.bak

**Track:** A. **Priority:** P1. **Type:** task.

**Why.** A `.bak` file next to a 12,008-line live file. Per AGENTS.md "No File Proliferation" this is forbidden.

**Method.** `diff` the two; identify any unique content in the .bak; merge into live or discard with permission. Then delete the .bak file.

**Acceptance.** No `.bak` files anywhere in `crates/`. Commit hash.

priority: 1
type: task

## [A6] br doctor sync repair

**Track:** A. **Priority:** P0. **Type:** bug.

**Why.** `br doctor` reports `WARN gitignore.beads_inner: Root .gitignore excludes .beads/.gitignore — br's ignore rules are ineffective` and `WARN db.sidecars: WAL sidecar exists without a matching SHM sidecar at .beads/beads.db-wal`. As a consequence, `br list --json` returned `{"issues": []}` while the JSONL contains 217 records — beads CLI is silently broken for *list* operations even though *create*/*close* work. This blocks Phase 3a bulk import (we need to verify created beads after import) and blocks any future agent's ability to find ready work.

**Method.**
1. Edit root `.gitignore` to *not* exclude `.beads/.gitignore` (remove the offending line).
2. Investigate the SHM sidecar missing — likely a result of mid-write daemon crash. Run `br doctor --fix` if available; otherwise checkpoint the WAL: `sqlite3 .beads/beads.db "PRAGMA wal_checkpoint(TRUNCATE);"`.
3. Re-import JSONL into the SQLite DB: `br sync --import` if it exists, else delete `beads.db` and re-import from JSONL.
4. Verify `br list --json | jq '.issues | length'` matches the JSONL line count.
5. Add a regression smoke: create issue, list, close, list — assert each step's output matches expectations.

**Acceptance.** `br doctor` reports zero WARN. `br list --json` returns 217 records. Smoke test committed under `tests/integration/br_smoke.sh`.

**Blocks:** all bead-tracker–dependent work, including the rest of Phase 3a.

priority: 0
type: bug

## [A7] pyproject.toml audit

**Track:** A. **Priority:** P2. **Type:** task.

**Why.** With `dist/` and the abi3 binary likely tracked, the build manifest probably has cruft. Plus the backend entry-point dispatch dict drift (F2) implies the package metadata may not be authoritative.

**Acceptance.** `pyproject.toml` reviewed line-by-line; deprecated entries removed; entry points verified against actual exports.

priority: 2
type: task

## [B1] Decide canonical conformance source: Rust harness vs. Python pytest

**Track:** B — Conformance & evidence. **Priority:** P0. **Type:** task.

**Why this is the foundational decision for Track B.** Today the project has two parallel conformance mechanisms: (a) the Rust `crates/fnx-conformance/` harness with 20+ test files, schemas, fixtures, and the entire G1→G8 gate topology described in SPEC §18; (b) the Python `tests/python/` parity suite with 1,392 passing tests against upstream NetworkX. The Rust harness is **stale** — `artifacts/conformance/latest/` has only 6 stub reports of 140-149 bytes each from Mar 19, while code was edited Apr 8 — and has been silently superseded by the Python suite. The Python suite is honest and active but does not emit any of SPEC §19's required artifacts (RaptorQ envelope, deterministic replay, normalized parity reports). FEATURE_PARITY.md and SPEC §15 still describe the Rust harness as authoritative, which is no longer true.

**Decision required.** One of:
- **Option A (recommended):** Promote the Python suite to Tier B (differential conformance per SPEC §8 ladder). Retire the Rust harness or keep only as a thin driver consuming pytest JSON output. Rewrite SPEC §8/§15/§18 and FEATURE_PARITY.md accordingly. Pro: matches reality, immediately usable. Con: requires rewriting the conformance reporting layer to emit RaptorQ-enveloped reports from pytest.
- **Option B:** Resurrect the Rust harness. Run it; regenerate fixtures; close the gap to the Python suite. Pro: matches SPEC verbatim. Con: duplicates work, requires keeping two oracles in sync forever.

**Recommendation.** Option A. The Python suite is the source of truth in practice; aligning docs to reality is cheaper than aligning reality to docs. Per AGENTS.md "Backwards Compatibility" clause ("we don't care about backwards compatibility, we want the RIGHT way with NO TECH DEBT") this is the right call.

**Acceptance.** Decision documented in this bead body. SPEC §8/§15/§18 and FEATURE_PARITY.md updated to reflect the chosen option. Subsequent Track B beads (B2-B12) updated to follow the chosen option.

**Blocks:** B2, B3, B4, B5, B6, B7, B8, B9, B10, B11, B12.

priority: 0
type: task

## [B2] Conformance regeneration: fresh reports for all fixtures

**Track:** B. **Priority:** P0. **Type:** task.

**Why.** `artifacts/conformance/latest/` contains 6 stub reports of <200 bytes each, all dated 2026-03-19 against code last edited 2026-04-08 — three weeks of drift. SPEC §8 calls Tier B (differential conformance) the *acceptance gate* for V1 release; today it cannot honestly be claimed.

**Method.** Per the option chosen in B1: re-run the conformance pipeline against current `main`; regenerate ALL fixture reports; commit them. Each report carries `{schema_version, fixture_id, fnx_commit, nx_version, status, mismatches[], duration_ms, witness_hash}`.

**Acceptance.** Every report under `artifacts/conformance/latest/` is dated within 24 hours of the commit creating it. The smoke report contains real test data, not `{"status":"passed"}`. Commit hash + report directory listing recorded.

**Blocked by:** B1.
**Blocks:** B3, B4.

priority: 0
type: task

## [B3] Wire RaptorQ envelope onto every conformance report

**Track:** B. **Priority:** P0. **Type:** feature.

**Why.** SPEC §19 mandates a canonical envelope schema for every persistent artifact: `{artifact_id, source_hash, raptorq{k, repair_symbols, symbol_hashes}, scrub{status}, decode_proofs[]}`. Today only the smoke report has a sidecar (`smoke_report.raptorq.json`). All other conformance reports are envelope-less, violating SPEC §9 RaptorQ-Everywhere Contract.

**Method.** Extend the conformance harness (or pytest reporter) to call `fnx-durability generate` on every emitted report. Validate the envelope against `artifacts/conformance/schema/v1/forensics_bundle_index_schema_v1.json` (or write a new schema if needed). Add a CI gate `crates/fnx-conformance/tests/envelope_schema_gate.rs` that fails on any envelope-less report.

**Acceptance.** Every report under `artifacts/conformance/latest/*.report.json` has a sibling `*.raptorq.json` whose `scrub.status: ok` and whose `source_hash` matches the report's blake3. Schema gate test passes.

**Blocked by:** B2.

priority: 0
type: feature

## [B4] Conformance freshness CI gate

**Track:** B. **Priority:** P0. **Type:** feature.

**Why.** Without a freshness gate, B2's regenerated reports will go stale within weeks. The same drift that produced today's situation will recur.

**Method.** Add `.github/workflows/conformance.yml` (or extend existing) to run as the *first* step of G2: compare `mtime` of every `artifacts/conformance/latest/*.report.json` against the most recent change to `crates/fnx-conformance/`, `crates/fnx-algorithms/`, or `python/franken_networkx/`. Fail the build if any report is older. Provide a `[skip-freshness]` PR label that pairs with auto-creation of a follow-up bead on merge to main (B4.1).

**Acceptance.** `.github/workflows/conformance.yml` exists. CI fails on a manufactured stale report. `[skip-freshness]` label tested.

**Blocked by:** B2, B3.

priority: 0
type: feature

## [B5] One-pipeline conformance: pytest emits Rust-consumable parity records

**Track:** B. **Priority:** P0. **Type:** feature.

**Why.** Per B1's expected Option-A outcome, the Python suite is the active oracle but the Rust harness still owns the schema vocabulary. Without a cross-walk, every bead in Tracks C, D, G that needs conformance evidence has to choose between two formats.

**Method.** Add a pytest reporter plugin (`tests/python/conftest.py`) that emits a structured JSON record per test: `{test_id, fixture_id, family, status, mismatches[], witness_hash, duration_ms}`. The format matches the Rust harness's report schema. Output goes to `artifacts/conformance/latest/pytest_parity_run.jsonl`. The Rust harness driver consumes it and produces the bundle reports B2-B4 expect.

**Acceptance.** A single `pytest tests/python/` run produces the canonical conformance bundle. The Rust harness no longer has its own oracle code path.

**Blocked by:** B1, B2.

priority: 0
type: feature

## [B6] Tier C: structure-aware property suite via proptest

**Track:** B. **Priority:** P1. **Type:** feature.

**Why.** SPEC §8 assurance ladder requires Tier C (property/fuzz/adversarial). Today Tier C is shallow — one fuzz target (adjlist), no property tests over algorithm invariants. The Tier B Python suite tests fnx vs NX on hand-picked graphs; it does not exercise properties like "shortest path is monotone in edge weight" across random graphs.

**Method.** For each algorithm family, define an invariant set:
- Shortest path: monotone in weight; triangle inequality; symmetric in undirected.
- Matching: max ≥ maximal ≥ min; never two edges share a vertex.
- PageRank: sums to 1.0 ± 1e-10; positive on every reachable node.
- Connected components: union of all component sets = node set; pairwise disjoint.
- Centrality: degree ≤ closeness rank for trees; bounded by [0,1] post-normalization.

Implement via `proptest` (Rust) and `hypothesis` (Python). 1000 graphs per family per CI run. Failures auto-minimize and quarantine.

**Acceptance.** `crates/fnx-algorithms/tests/proptest_invariants.rs` exists. CI runs it. Failures produce minimized counter-example fixtures committed under `crates/fnx-conformance/fixtures/regressions/`.

**Blocked by:** B5.

priority: 1
type: feature

## [B6.1] Re-enable hypothesis suite in nightly CI

**Track:** B. **Priority:** P1. **Type:** task.

**Why.** `tests/python/test_hypothesis.py` exists but was excluded from the smoke run for time. Hypothesis is the Python equivalent of proptest and complements B6.

**Acceptance.** Nightly CI runs hypothesis with a 10-min budget; database committed under `.hypothesis/`.

priority: 1
type: task

## [B6.2] Include test_error_messages.py in parity gate

**Track:** B. **Priority:** P1. **Type:** task.

**Why.** AGENTS.md L102 mentions this file but it's not currently in the active parity gate. Error message wording matters for user perception of "drop-in" status.

priority: 1
type: task

## [B7] Tier C: differential fuzzing fnx vs NX

**Track:** B. **Priority:** P1. **Type:** feature.

**Why.** Continuous drift detection. The current model is "snapshot conformance every so often"; differential fuzzing makes drift detection continuous.

**Method.** A cargo-fuzz harness that generates random graphs (via `arbitrary::Arbitrary`), invokes both fnx and NX (via PyO3 callback), normalizes outputs, and asserts equality. Any disagreement minimizes the graph and auto-creates a quarantine-tagged bead.

**Acceptance.** `fuzz/fuzz_targets/diff_fnx_vs_nx.rs` exists. CI 60s/PR, 24h/nightly. Quarantine-tag flow tested.

**Blocked by:** B5, B6. **Blocks:** G3.

priority: 1
type: feature

## [B8] Tier D: historical regression corpus with provenance

**Track:** B. **Priority:** P1. **Type:** feature.

**Why.** SPEC §8 ladder Tier D. Every fixture that has ever caught a bug must stay in the corpus, preventing silent regression of past bugs.

**Method.** Convention: when a bead closes with a bug fix, the minimized fixture lands at `crates/fnx-conformance/fixtures/regressions/<bead-id>/`. CI runs the full regression corpus on every PR.

**Acceptance.** Convention documented in `AGENTS.md` (under "Testing"). Corpus directory exists. CI runs it.

**Blocks:** G4.

priority: 1
type: feature

## [B9] Cross-walk between Python parity tests and Rust conformance harness

**Track:** B. **Priority:** P1. **Type:** task.

**Why.** Per B5 outcome, this bead may be subsumed; if not, it's the explicit cross-walk doc.

priority: 1
type: task

## [B10] View-coherence fixtures (SPEC §15 row 2)

**Track:** B. **Priority:** P1. **Type:** feature.

**Why.** SPEC §15 conformance matrix lists "view behavior and cache reset" as `high` severity. Currently absent from the corpus.

**Method.** Fixtures exercising mutation-during-iteration, cache invalidation under concurrent reads, revision-counter monotonicity. Add B10.1 for a `loom`-based test of view cache thread safety.

**Acceptance.** ≥6 fixtures per view type committed.

priority: 1
type: feature

## [B11] Conformance dashboard

**Track:** B. **Priority:** P1. **Type:** feature.

**Why.** A generated `artifacts/conformance/dashboard.html` showing per-family pass rate, drift count, freshness, sidecar status. Linked from README. Public-facing trust signal. Add B11.1: per-PR contributor view with diff highlighting.

priority: 1
type: feature

## [B12] Round-trip identity tests for every parser × graph type

**Track:** B. **Priority:** P1. **Type:** feature.

**Why.** Today's parity tests check fnx vs NX. They do *not* check that fnx → format → fnx is identity. Round-trip drift would be invisible.

**Method.** For each (parser, graph_type) pair, generate a graph, write, parse, assert deep equality. Cross-format too (write GraphML, parse, write JSON, parse, assert equality up to format-specific limitations).

priority: 1
type: feature

## [C1] CGSE decision: implement (recommended) vs. retract

**Track:** C — CGSE crown jewel. **Priority:** P0. **Type:** task.

**Why this is the project's most strategic decision.** README §"What Makes This Project Special": "Canonical Graph Semantics Engine (CGSE): deterministic tie-break policies with complexity witness artifacts per algorithm family. This is treated as a core identity constraint, not a best-effort nice-to-have." SPEC §0 calls it the "Crown-jewel innovation." Yet the actual code has only `CGSE_POLICY_SCHEMA_VERSION_V1` constants and a `CgseValue` enum in `crates/fnx-runtime/src/lib.rs`. No tie-break decision dispatch, no complexity witness emission, no per-family policy lookup. Either the README is lying, or the engine needs to be built.

**Per AGENTS.md "Backwards Compatibility" clause** ("we don't care about backwards compatibility, we want the RIGHT way with NO TECH DEBT"), the default should be **implement**. Retracting would cost the project its claimed differentiator vs every other NetworkX port. The expanded plan in C2-C9 makes CGSE a research-grade contribution: 12 named tie-break policies, type-checked per algorithm family, compile-time verified, complexity-witnessed via Merkle decision-path hashes, adversarial-corpus-tested against NX, counter-example mined via SAT minimization, and exposed to Python users via a public witness-capture API.

**Decision recommended:** **Implement** per C2-C9. If the user disagrees, retract by rewriting README §"What Makes This Project Special" to honestly describe what's special (large native algorithm corpus + working backend mode + multi-graph parity).

**Acceptance.** Decision documented. README/SPEC updated to reflect choice. C2-C9 either green-lit or formally retracted.

**Blocks:** C2.

priority: 0
type: task

## [C2] CGSE TieBreakPolicy type with 12 instantiations

**Track:** C. **Priority:** P0. **Type:** feature.

**Why.** Each NetworkX-observable ordering quirk needs a *name*. Without named policies, "deterministic tie-break" is hand-wavy; with them, every algorithm declares its policy and divergence is detectable.

**Method.** New crate `fnx-cgse`. `TieBreakPolicy` is a closed sum type:
1. `LexMin` 2. `LexMax` 3. `InsertionOrder` 4. `ReverseInsertionOrder` 5. `WeightThenLex` 6. `LexThenWeight` 7. `DeterministicHashSeeded(u64)` 8. `DegreeMinThenLex` 9. `DegreeMaxThenLex` 10. `DfsPreorder` 11. `BfsLevelLex` 12. `EdgeKeyLex`.

Algorithm families take `Policy: const TieBreakPolicy` as a const generic. Compile-time check via `#[cfg(test)]` exhaustiveness. Add C2.1: monomorphization-cost measurement; if compile time delta > 20%, switch to runtime dispatch.

**Acceptance.** `crates/fnx-cgse/` crate added; type defined; 12 unit tests proving each variant's ordering. Compile-time measurement before/after recorded.

**Blocked by:** C1. **Blocks:** C3.

priority: 0
type: feature

## [C3] ComplexityWitness type with Merkle decision-path hash

**Track:** C. **Priority:** P0. **Type:** feature.

**Why.** A "complexity witness" without a fingerprint is just a runtime counter. The Merkle hash makes two runs verifiable as taking the *same path* on the same graph — drift becomes a hash mismatch.

**Method.** `pub struct ComplexityWitness { pub n: usize, pub m: usize, pub dominant_term: Symbol, pub observed_count: u64, pub policy_id: PolicyId, pub seed: Option<u64>, pub decision_path_blake3: [u8; 32] }`. Algorithms acquire `&mut WitnessSink` and call it on every tie-break; the sink updates a streaming blake3 hasher.

**Acceptance.** Type defined; sink implementation with thread-local ring buffer; flush to `WitnessLedger`. Unit test: same graph + same algorithm + same policy ⇒ same `decision_path_blake3`.

**Blocked by:** C2. **Blocks:** C4.

priority: 0
type: feature

## [C4] Wire 12 reference algorithms through CGSE

**Track:** C. **Priority:** P0. **Type:** feature.

**Why.** One per policy variant: dijkstra, bellman_ford, bfs, dfs, max_weight_matching, min_weight_matching, connected_components, strongly_connected_components, kruskal, prim, eulerian_circuit, topological_sort.

**Method.** For each algorithm: declare its policy at the type level; replace its current ordering decisions with calls into the policy; emit witnesses on every tie-break call; existing parity tests must still pass.

**Acceptance.** 12 algorithms refactored. Existing 1392-test pytest suite remains green. Witness records visible via `cargo test -p fnx-cgse --nocapture`.

**Blocked by:** C3. **Blocks:** C5.

priority: 0
type: feature

## [C5] CGSE adversarial tie-break corpus

**Track:** C. **Priority:** P1. **Type:** feature.

**Why.** Without a *deliberately tie-saturated* corpus, CGSE's correctness claim is unproven. A graph with all distinct edge weights doesn't exercise tie-break code at all.

**Method.** Generator (seeded, deterministic) building graphs that maximize equal-cost / equal-weight ties for each algorithm family. ≥50 graphs per family. For each, run NX as oracle and fnx side-by-side; assert path equality AND witness-hash equality.

**Acceptance.** 600+ adversarial fixtures. Both equality assertions pass.

**Blocked by:** C4. **Blocks:** C6, G3.

priority: 1
type: feature

## [C6] Counter-example mining loop

**Track:** C. **Priority:** P1. **Type:** feature.

**Why.** Continuous drift detection for CGSE specifically.

**Method.** Nightly CI job uses `proptest` to search for fnx vs NX disagreement on tie-break. Disagreements auto-create quarantine-tagged beads with minimized graphs.

priority: 1
type: feature

## [C7] Per-family witness artifacts under artifacts/cgse/witnesses/

**Track:** C. **Priority:** P1. **Type:** feature.

**Why.** Make the README claim literally true: complexity witness artifacts per algorithm family.

**Method.** `artifacts/cgse/witnesses/<family>/<date>.witnesses.jsonl` with RaptorQ sidecars per SPEC §19.

priority: 1
type: feature

## [C8] Complexity oracle: assert observed counts match analytic formulas

**Track:** C. **Priority:** P2. **Type:** feature.

**Why.** SPEC §17 mandates "complexity regressions for adversarial classes" gating. The witness counts make this measurable.

**Method.** For each algorithm family, encode the complexity formula; assert observed_count is within constant factor across the corpus.

priority: 2
type: feature

## [C9] Public CGSE API for Python

**Track:** C. **Priority:** P2. **Type:** feature.

**Why.** Make CGSE a user-visible feature: `with fnx.cgse.witness_capture() as w: fnx.dijkstra(G); print(w.decisions)`.

**Non-goal V1:** users cannot define new policies (closed type).

priority: 2
type: feature

## [D1] Strict/Hardened mode decision: implement (recommended) vs. retract

**Track:** D — Modes. **Priority:** P0. **Type:** task.

**Why.** SPEC §4 makes the mode split central to the project's identity. AGENTS.md "Compatibility Doctrine" repeats it. Yet `CompatibilityMode::{Strict, Hardened}` is enum-only — no algorithm or parser branches on it. Per AGENTS.md backwards-compat clause, default is **implement**.

**Decision recommended.** Implement per D2-D9. The expanded plan goes beyond the SPEC's literal reading and turns the modes into a Bayesian admission controller with calibrated confidence (per SPEC §6 alien-artifact decision contract, currently zero-implemented).

**Acceptance.** Decision documented. SPEC §4/§16 updated. D2-D9 either green-lit or formally retracted.

**Blocks:** D2.

priority: 0
type: task

## [D2] RuntimePolicy threaded through parsers and high-risk algorithms

**Track:** D. **Priority:** P0. **Type:** feature.

**Why.** Today the modes are types with no callers.

**Method.** `RuntimePolicy { mode, allowlist, decision_log, posterior, loss_matrix }` value constructed per-call (not global). Every parser in `fnx-readwrite` and every "high-risk" algorithm (parser entry points, dispatch decisions) takes it as an argument or thread-local context.

**Acceptance.** `RuntimePolicy` flows through all parsers. Existing tests still pass with default `Strict` mode.

**Blocked by:** D1. **Blocks:** D3, D4.

priority: 0
type: feature

## [D3] Strict-mode fail-closed parser fixtures

**Track:** D. **Priority:** P0. **Type:** feature.

**Why.** SPEC §16 fail-closed-on-unknown-metadata rule.

**Method.** 24 strict fixtures (6 per format × 4 formats: gml/graphml/json/adjlist) proving fail-closed on malformed inputs.

**Acceptance.** 24 fixtures committed; conformance gate runs them in strict mode; all fail closed with documented error type.

**Blocked by:** D2.

priority: 0
type: feature

## [D4] Hardened-mode Bayesian admission controller

**Track:** D. **Priority:** P0. **Type:** feature.

**Why.** SPEC §6 alien-artifact decision contract.

**Method.** Posterior `P(input_safe | evidence)` updated from parser warnings, attribute anomalies, density anomalies. Recovery action minimizes expected loss under D5's loss matrix. 24 hardened fixtures (mirror of D3) prove same inputs recover with audit trail.

**Acceptance.** 24 fixtures; controller code; tests proving recovery action and posterior update visible in decision ledger.

**Blocked by:** D5 (need loss matrix to act).

priority: 0
type: feature

## [D5] Loss matrix calibration with Bayesian shrinkage prior

**Track:** D. **Priority:** P1. **Type:** feature.

**Why.** SPEC §6 row 3 mandates "loss matrix with asymmetric costs." Calibrated against the adversarial fixture corpus, not guessed. With small samples, hierarchical shrinkage prevents noisy estimates.

**Method.** `LossMatrix { false_accept_cost, false_reject_cost, late_detect_cost, recovery_cost }` per parser × per attack class. Calibrated via empirical Bayes on the D3+D4 fixtures using a hierarchical model (parser as group, attack class as level).

**Acceptance.** Calibration code; calibrated values committed under `artifacts/cgse/loss_matrix_v1.json` with provenance.

**Blocks:** D4.

priority: 1
type: feature

## [D6] Calibrated confidence with Brier score gate

**Track:** D. **Priority:** P1. **Type:** feature.

**Why.** SPEC §6 rows 4-5 mandate calibrated confidence + drift alarm.

**Method.** Every recovery decision emits `confidence: f32`. CI gate: aggregate Brier score across the corpus < 0.10. Drift alarm opens a beads issue if exceeded.

priority: 1
type: feature

## [D7] Decision ledger with versioned schema

**Track:** D. **Priority:** P1. **Type:** feature.

**Why.** SPEC §6 evidence ledger. Today the ledger types exist in `fnx-runtime` but no algorithm writes to them.

**Method.** Every mode-mediated decision writes a record `{ts, parser, mode, evidence_signals, posterior_before, posterior_after, action, confidence, loss_estimate}` to `artifacts/conformance/latest/decision_ledger.jsonl` with RaptorQ sidecar. Schema versioned; CI validates.

**Blocks:** D8.

priority: 1
type: feature

## [D8] Drift ledger feedback: weekly under-confident region report

**Track:** D. **Priority:** P1. **Type:** feature.

**Why.** Closes the SPEC §16 "explicit drift ledger" loop.

**Method.** Weekly CI job reads `decision_ledger.jsonl`; clusters decisions by `confidence < 0.5`; creates beads issues to expand fixture coverage in under-confident regions.

priority: 1
type: feature

## [D9] Mode-stamped conformance reports

**Track:** D. **Priority:** P1. **Type:** feature.

**Why.** Strict and hardened modes produce different observable behaviors; each needs its own report bundle.

**Method.** `artifacts/conformance/latest/*.strict.report.json`, `*.hardened.report.json`. Divergence metric tracked.

priority: 1
type: feature

## [E1] Restore SLOs to SPEC §17 values (or per-row rationale)

**Track:** E — Performance, durability, fuzz, CI gates. **Priority:** P0. **Type:** bug.

**Why this is critical and time-sensitive.** Commit 742c48e (Apr 7) relaxed `artifacts/perf/slo_thresholds.json` in three places: graph_serialization min throughput **45 → 1.5 MB/s (30×)**, memory regression baseline **220 → 400 MB**, p99 tail regression **650 → 2000 ms**. SPEC §7 acceptance rule: "no optimization is accepted without associated correctness evidence." A relaxation is a *negative optimization* and the same rule applies — it requires profile evidence, behavior-isomorphism proof, and explicit documentation. None was provided. The relaxation silently downgrades the project's performance guarantee.

**Method.** Per row that was relaxed:
1. Revert to pre-742c48e value (`git show 742c48e^:artifacts/perf/slo_thresholds.json`).
2. Run the perf workload (E2 must exist for this).
3. If the original budget passes: commit the revert.
4. If not: write `artifacts/perf/slo_downgrade_rationale_<row>.md` containing (a) flamegraph, (b) optimization levers tried, (c) behavior-isomorphism proof from B-track conformance, (d) user-impact analysis, (e) the new budget. Per-row downgrades only. No blanket relaxation.

**Acceptance.** Either reverted commit hash, OR `slo_downgrade_rationale_*.md` present with all 5 sections per relaxed row.

**Blocks:** E3, E4.

priority: 0
type: bug

## [E2] Benchmark workloads for all 8 SLO rows

**Track:** E. **Priority:** P1. **Type:** task.

**Why.** Bead `franken_networkx-16ds` ("PERF: Add algorithm-family benchmark workloads to activate all 8 SLO thresholds") was closed yesterday. Verify completion. If incomplete, finish it. Each workload uses adversarial graph classes per SPEC §17 (power-law degree, max-density, expander, path-like) — not just gnp.

**Acceptance.** All 8 SLO rows have at least one named benchmark workload exercising them on adversarial classes.

**Blocks:** E3, G0.

priority: 1
type: task

## [E3] Profile-and-prove optimization loop per SLO row

**Track:** E. **Priority:** P1. **Type:** feature.

**Why.** SPEC §7 mandates profile→one-lever→prove→re-baseline. Today only 1 proof artifact exists (`artifacts/perf/proof/2026-02-14_graph_kernel_clone_elision.md`). Need 8.

**Method.** For each SLO row missing budget: (1) baseline percentiles, (2) `cargo flamegraph` profile committed under `artifacts/perf/proof/<bead>/flamegraph.svg.gz` (compressed; see E3.1), (3) one-lever change, (4) behavior-isomorphism proof from conformance corpus, (5) re-baseline percentiles, (6) delta artifact.

**Acceptance.** ≥8 proof artifacts under `artifacts/perf/proof/`.

**Blocked by:** E1, E2.

priority: 1
type: feature

## [E4] Wire scripts/run_benchmark_gate.sh into perf CI workflow

**Track:** E. **Priority:** P0. **Type:** feature.

**Why.** SPEC §18 G6 requires perf gate fail-closed in CI. Today the script exists but nothing runs it on PR.

**Method.** `.github/workflows/perf.yml` runs `scripts/run_benchmark_gate.sh`, attaches percentile artifacts, posts diff-vs-baseline as PR comment. Includes `regression_envelope.json` per SPEC §18.

**Blocked by:** E1.

priority: 0
type: feature

## [E5] Wire G1→G8 CI gate topology into conformance CI workflow

**Track:** E. **Priority:** P0. **Type:** feature.

**Why.** SPEC §18 prescribes G1→G8 fail-closed gates. `crates/fnx-conformance/tests/ci_gate_topology_gate.rs` exists locally; nothing runs it on PR.

**Method.** `.github/workflows/conformance.yml` runs G1→G8 in order, short-circuits on first miss, emits failure envelope with deterministic-replay command per SPEC §18.

priority: 0
type: feature

## [E6] Cargo-fuzz harnesses for every parser

**Track:** E. **Priority:** P1. **Type:** feature.

**Why.** SPEC §5 mandates fuzz coverage of high-risk parsers. Today only adjlist has a fresh fuzz target (commit ecb229e).

**Method.** `edgelist_fuzz`, `graphml_fuzz`, `gml_fuzz`, `json_fuzz`, `pajek_fuzz`, `node_link_fuzz`, plus `attribute_value_fuzz` for type-confusion attacks. Each runs 60s in PR CI, 24h on nightly. Crash corpus committed.

priority: 1
type: feature

## [E7] Structure-aware fuzzers for algorithm code paths

**Track:** E. **Priority:** P1. **Type:** feature.

**Why.** Parser fuzzers can't reach algorithm-level bugs.

**Method.** `arbitrary::Arbitrary` for graph types; one fuzz target per algorithm family.

**Blocked by:** E6.

priority: 1
type: feature

## [E8] RaptorQ-everywhere coverage expansion

**Track:** E. **Priority:** P1. **Type:** feature.

**Why.** SPEC §9 enumerates 5 categories of long-lived artifact requiring RaptorQ sidecars: conformance fixture bundles, benchmark baseline bundles, migration manifests, reproducibility ledgers, long-lived state snapshots. Today only smoke reports get sidecars.

**Method.** Audit `artifacts/`; for each long-lived file matching the SPEC §9 list, generate a sidecar via `fnx-durability generate`. Add CI gate.

**Acceptance checklist:**
- [ ] Conformance fixture bundles
- [ ] Benchmark baseline bundles
- [ ] Migration manifests
- [ ] Reproducibility ledgers
- [ ] Long-lived state snapshots

**Blocks:** E9.

priority: 1
type: feature

## [E9] Continuous decode-drill in CI

**Track:** E. **Priority:** P1. **Type:** feature.

**Why.** SPEC §19 says decode proofs must be emitted per recovery event. Today this is theoretical.

**Method.** Every CI run picks a random committed sidecar, deletes 30% of repair symbols, runs `fnx-durability decode-drill`, emits decode proof under `artifacts/conformance/latest/decode_proofs/`.

**Blocked by:** E8.

priority: 1
type: feature

## [E10] Adversarial decode-drill: success bounds and fail-closed beyond

**Track:** E. **Priority:** P2. **Type:** feature.

**Why.** Recovery success bounds must be proven, not assumed.

**Method.** Pre-corrupt 1, 5, 50%, 100% of packets. Assert recovery up to published RaptorQ overhead ratio; fail-closed beyond.

priority: 2
type: feature

## [E11] Memory regression profiling with dhat/heaptrack

**Track:** E. **Priority:** P2. **Type:** feature.

**Why.** Memory budget was doubled in commit 742c48e (220 → 400 MB) without justification. SPEC §17 +10% rule unmet.

**Method.** Per-fixture peak-RSS measurement via `dhat` or `heaptrack`; commit reports under `artifacts/perf/memory/<fixture>/`. Gate: regression ≤ +10%.

priority: 2
type: feature

## [E12] Tail-stability gate: 30-sample p99 distribution shift

**Track:** E. **Priority:** P2. **Type:** feature.

**Why.** p99 budget was tripled in commit 742c48e (650 → 2000 ms) without justification.

**Method.** Per-family p99 measured 30 times in CI; gate fails if distribution shift > +10%.

priority: 2
type: feature

## [F1] Final NX-REPLACE wave: eliminate _to_nx and _networkx_compat_graph residue

**Track:** F — Long-tail polish. **Priority:** P0. **Type:** task.

**Why.** Despite the recent NX-REPLACE wave (commits 69f8cc5, c69eb98), `python/franken_networkx/__init__.py` still contains 15 `_to_nx` references and 4 `_networkx_compat_graph` proxy references. The 100% top-level parity claim is blocked on these.

**Method (F1.1).** Use `ast-grep` per AGENTS.md guidance to confirm true call-site count (raw `grep -c` may include comments/literals). For each true call site:
- Either implement the function natively in Rust (preferred) and update the wrapper, OR
- Mark with `# DELEGATED_TO_NETWORKX` comment and exclude from parity claims (F3 coverage matrix).

**Acceptance.** `ast-grep` confirms `_to_nx` count = 0, `_networkx_compat_graph` count = 0. Each delegated function has the explicit marker. Parity test suite still 1392/0/54 or better.

**Blocks:** F3.

priority: 0
type: task

## [F2] Auto-discovery for backend dispatch

**Track:** F. **Priority:** P1. **Type:** feature.

**Why.** `python/franken_networkx/backend.py:_SUPPORTED_ALGORITHMS` is a hand-curated dict (~80 entries). Adding a new Rust algorithm does not auto-extend backend dispatch — meaning `nx.config.backend_priority = ["franken_networkx"]` silently falls back for everything not in the dict.

**Method.** Replace the hard-coded dict with a generated registry sourced from a single Rust manifest. Adding a new Rust algorithm auto-extends backend coverage.

**Acceptance.** Zero hand maintenance for backend dispatch. Adding a new function in `crates/fnx-python/src/algorithms.rs` auto-registers it.

priority: 1
type: feature

## [F3] Generated coverage matrix: machine-checked parity claims

**Track:** F. **Priority:** P0. **Type:** feature.

**Why.** FEATURE_PARITY claims "100% NX top-level function parity (731+)" and "83 functions delegate to NX" but these numbers are not backed by a generated artifact. Without a coverage matrix, the parity claim is unauditable.

**Method.** A script that walks `python/franken_networkx/__init__.py`, classifies each export as `RUST_NATIVE` / `PY_WRAPPER` / `NX_DELEGATED`, and writes `docs/coverage.md`. CI gate: zero unclassified.

**Acceptance.** `docs/coverage.md` generated; CI gate active; FEATURE_PARITY.md replaces the marketing claim with a link to the generated file.

**Blocked by:** F1.

priority: 0
type: feature

## [F4] Triage 54 currently-skipped Python tests

**Track:** F. **Priority:** P1. **Type:** task.

**Why.** Each `pytest.skip()` is either a known gap, an untracked TODO, or a flake. They need categorization + bead-tracking.

**Method (F4.1).** Each skip must have a `reason` literal; CI gate fails on bare skips. Then triage: cluster reasons; open one bead per cluster.

priority: 1
type: task

## [F5] Update FEATURE_PARITY.md to reflect actual reality

**Track:** F. **Priority:** P1. **Type:** task.

**Why.** Most rows say `in_progress`; that's honest. Marketing claims like "100% top-level function parity" are not. Replace with link to F3 generated matrix.

**Method (F5.1).** Define `parity_green` operationally: zero strict-mode drift on the full Tier B corpus + zero open `parity_gap` beads + freshness < 24h.

priority: 1
type: task

## [F6] Update README "Current State" and "Next Steps" with HEAD snapshot

**Track:** F. **Priority:** P1. **Type:** task.

**Why.** README "Current State" lists 7 vertical slices that pre-date 90% of the algorithm corpus. "Next Steps" items 1-5 are stale.

**Method.** Generate snapshot from `git log` + `br list --status=closed --json` (most recent 20 closures). Replace "Next Steps" with the Track A-E plan from this bridge.

priority: 1
type: task

## [F7] Refresh CHANGELOG.md from commit history

**Track:** F. **Priority:** P1. **Type:** task.

**Why.** Last entry was 2026-03-22; ~50 commits since.

**Method (F7.1).** `scripts/regenerate_changelog.py` from `git log` + closed beads. Make it part of release flow.

priority: 1
type: task

## [F8] Backend dispatch coverage measurement and gap report

**Track:** F. **Priority:** P1. **Type:** task.

**Why.** Quantify what fraction of NX top-level functions actually dispatch to fnx in backend mode.

**Acceptance.** `artifacts/coverage/backend_dispatch_coverage.json` with `{covered, total, ratio}` per family.

priority: 1
type: task

## [F9] CI gate: README/FEATURE_PARITY/CHANGELOG freshness vs HEAD~50

**Track:** F. **Priority:** P1. **Type:** feature.

**Why.** Without a freshness gate, doc drift will recur.

**Method.** CI fails if `README.md`, `FEATURE_PARITY.md`, or `CHANGELOG.md` is older than HEAD~50 commits.

priority: 1
type: feature

## [F10] Cross-platform CI matrix

**Track:** F. **Priority:** P2. **Type:** feature.

**Why.** README implies cross-platform wheels via abi3-py310. Actual cross-platform support is unverified.

**Method.** GitHub Actions matrix: Linux × macOS × Windows × Python 3.10/3.11/3.12/3.13. Build wheel + run pytest smoke per cell.

priority: 2
type: feature

## [F11] Error message parity audit

**Track:** F. **Priority:** P1. **Type:** task.

**Why.** NX has carefully-tuned error messages; "drop-in" status requires parity here too.

**Method.** Every `raise` in `fnx-algorithms` and `fnx-readwrite` matches NX's wording within Levenshtein-3.

priority: 1
type: task

## [F12] CI runs every examples/*.py end-to-end on every PR

**Track:** F. **Priority:** P1. **Type:** feature.

**Why.** README L93-96 lists 4 examples. Are they runnable on current code? Should be CI-verified.

priority: 1
type: feature

## [F13] OSS hygiene files: SECURITY.md, CONTRIBUTING.md, CODE_OF_CONDUCT.md

**Track:** F. **Priority:** P2. **Type:** task.

priority: 2
type: task

## [G0] Wait for ≥30 historical perf runs in artifacts/perf/history/

**Track:** G — Crown-jewel multipliers. **Priority:** P3. **Type:** task.

**Why.** G1 (conformal bands) and G2 (GPD tail modeling) need ≥30 samples to be statistically valid. This bead is a precondition gate.

**Blocked by:** E2, E4. **Blocks:** G1, G2.

priority: 3
type: task

## [G1] Conformal-prediction performance bands

**Track:** G. **Priority:** P3. **Type:** feature.

**Why.** Fit a split-conformal regressor on (graph_features → runtime); emit per-PR prediction band with calibrated coverage. Distribution-free perf gating with finite-sample guarantees. No NetworkX port does this.

**Candidate dependency.** `linfa` (Rust ML) or hand-rolled.

**Blocked by:** G0.

priority: 3
type: feature

## [G2] Bayesian rare-event estimation for tail latency (GPD modeling)

**Track:** G. **Priority:** P3. **Type:** feature.

**Why.** p99/p99.9 from 30 samples is statistically nonsense. Generalized Pareto tail modeling (Peaks-Over-Threshold) gives posterior distributions with credible intervals.

**Candidate dependency.** `evd` crate or hand-rolled GPD MLE.

**Blocked by:** G0.

priority: 3
type: feature

## [G3] Witness-hash → SAT counter-example mining for CGSE

**Track:** G. **Priority:** P3. **Type:** feature.

**Why.** When B7 differential fuzzing finds a divergence, encode it as a SAT instance and minimize.

**Blocked by:** B7, C5.

priority: 3
type: feature

## [G4] Graph-isomorphism-aware regression deduplication

**Track:** G. **Priority:** P3. **Type:** feature.

**Why.** Regression corpus will accumulate near-duplicates over time.

**Blocked by:** B8.

priority: 3
type: feature

## [G5] Information-theoretic fuzz prioritization

**Track:** G. **Priority:** P3. **Type:** feature.

**Why.** Weight inputs by KL divergence of code-coverage histogram from historical mean. libFuzzer custom mutator.

priority: 3
type: feature

## [G6] Algebraic effect tracking for parser modes

**Track:** G. **Priority:** P3. **Type:** feature.

**Why.** Encode parser side-effects as a type-level effect row; mode-divergence regressions become compile errors.

priority: 3
type: feature

## [G7] Persistent-homology graph fingerprinting for fixture clustering

**Track:** G. **Priority:** P3. **Type:** feature.

**Why.** Detect when corpus over-samples a topological class; auto-suggest gaps.

**Candidate dependency.** No mature Rust crate; would need to build atop `nalgebra`.

priority: 3
type: feature

## [G8] Compressed-sensing replay logs (count-min sketch + reservoir)

**Track:** G. **Priority:** P3. **Type:** feature.

**Why.** Decision/witness ledgers grow forever; bounded summary alongside full log.

priority: 3
type: feature

## [G9] Optimal-transport fixture diversity (Wasserstein on graph spectra)

**Track:** G. **Priority:** P3. **Type:** feature.

**Why.** Principled answer to "how do we know we have enough fixtures?"

priority: 3
type: feature

## [G10] Differentiable graph layout for benchmark dashboard visualization

**Track:** G. **Priority:** P3. **Type:** feature.

**Why.** Conformance dashboard becomes a force-directed map of fixtures colored by drift status; humans see clusters.

priority: 3
type: feature

## [H1] Risk notes per track per the project's existing template

**Track:** H — Cross-cutting governance. **Priority:** P1. **Type:** task.

**Why.** AGENTS.md "Required evidence for substantive changes" lists "risk-note update if threat or compatibility surface changed." Template at `artifacts/phase2c/templates/risk_note.md`.

**Method.** Each track (A-G) gets one `artifacts/risk_notes/<track>_risk_note.md`. Filed before the track's first P0 lands.

priority: 1
type: task

## [H2] Threat-model notes per major subsystem

**Track:** H. **Priority:** P1. **Type:** task.

**Why.** SPEC §5 mandates "threat model notes for each major subsystem." Currently absent.

**Subsystems requiring notes.** `fnx-readwrite` (parser attack surface), `fnx-runtime` (mode dispatch + decision ledger), `fnx-dispatch` (backend route confusion), `fnx-durability` (artifact tampering), `fnx-classes` (mutation invariants), `fnx-views` (cache coherence under concurrency).

priority: 1
type: task

## [H3] RFC process for strict/hardened mode boundary changes

**Track:** H. **Priority:** P2. **Type:** task.

**Why.** Mode boundaries are load-bearing for the security doctrine; changes need deliberation, not drive-by edits.

**Method.** Proposed in `docs/rfc/`, voted on by tagging the bead with `rfc-required`.

priority: 2
type: task

## [H4] Quarterly compliance audit recurring bead

**Track:** H. **Priority:** P2. **Type:** task.

**Why.** Walks every claim in README + SPEC and reverifies. Schedules itself via `bv --robot-forecast`.

priority: 2
type: task

## [H5] Last-known-good snapshot tagging on every G1→G8 success

**Track:** H. **Priority:** P2. **Type:** feature.

**Why.** One-command rollback. Tags `lkg-YYYY-MM-DD-HHMM` per success.

priority: 2
type: feature
