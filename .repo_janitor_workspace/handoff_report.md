# Git Repo Janitor — Handoff Report

- produced_at: 2026-06-04 (UTC) | produced_by: git-repo-janitor | mode: full | variant: Quick
- repo: /data/projects/franken_networkx | primary_branch: main | archetype: polyglot-monorepo
- pre-cleanup HEAD: fb14e5468 | final HEAD: 13d170a56
- backup ref: refs/repo-janitor-backup/2026-06-04-pre-cleanup @ fb14e5468
- recovery bundle: .repo_janitor_workspace/recovery-bundle-2026-06-04/ (25 files, byte-verified, 0 mismatches)

## Context
Committed junk was confined to ~25 markdown docs stranded at the repo root. Untracked
scratch (out.txt, probe_*.py, perf.data, a.out, *.bak, storage.sqlite3, fuzz logs) was
already covered by a comprehensive .gitignore and never tracked.

## Actions (4 commits on main; no recovery branch — shared multi-agent checkout, per user)

### 08f2d385a — MOVE: 8 historical docs -> docs/history/ (git mv, rename-preserving)
FRANKENSQLITE_CROSSWALK.md, PARITY-COVERAGE.md, PHASE2C_EXTRACTION_PACKET.md,
REALITY_CHECK.md, REALITY_CHECK_BRIDGE_PLAN_2026-04-08.md, audit_networkx_fuzz.md,
audit_networkx_reality.md, UPGRADE_LOG.md. Zero inbound refs from retained files.

### efa087f18 — DELETE: 11 ephemeral TODO_*.md execution trackers (git rm)
Already matched by existing .gitignore rule `TODO_*.md`; committed before that rule existed.

### 83a1b09c2 — GITIGNORE: add .skill-loop-progress.md + perf.data.old

### 13d170a56 — UNTRACK: .skill-loop-progress.md (git rm --cached, private-index CAS)
271KB leaked slash-skill loop output. Untracked (not force-deleted) because a running
loop is actively appending to it; file preserved on disk, now gitignored.

## KEPT IN PLACE (load-bearing — moving would break the build)
- FEATURE_PARITY.md            -> CI gate G0 docs-freshness (.github/workflows/ci.yml:33)
- EXHAUSTIVE_LEGACY_ANALYSIS.md -> conformance test doc_pass00_gap_matrix_gate.rs:62 + 2 scripts
- EXISTING_NETWORKX_STRUCTURE.md -> same conformance test + scripts + SECURITY.md threat model
- COMPREHENSIVE_SPEC_FOR_FRANKENNETWORKX_V1.md -> README link (V1 spec)
- PROPOSED_ARCHITECTURE.md     -> reference_specs/ spec (3 refs)
- PLAN_TO_PORT_NETWORKX_TO_RUST.md -> kept per user (prose refs from retained spec docs)

## Verification
- No dangling functional references to any moved/deleted path from CI/test/script/source (git-grep clean).
- doc-gap conformance test's required docs all still present at repo root.
- Zero .rs/.py/.toml/test files in any janitor commit (doc-relocation only -> full cargo suite not warranted).
- No peer-staged files (lib.rs, __init__.py, perf artifacts) swept into any janitor commit.

## Recovery recipes
- Undo a move:   git checkout fb14e5468 -- <old-root-path>   (or git revert 08f2d385a)
- Undo deletes:  git checkout fb14e5468 -- <TODO_*.md>        (or git revert efa087f18)
- Restore from bundle: cp .repo_janitor_workspace/recovery-bundle-2026-06-04/working-tree-copies/<path> <path>

## Follow-ups for the user
- Push not performed (skill never pushes). To publish + mirror per AGENTS.md:
    git push origin main
    git push origin main:master
- Bundle + workspace left in place under .repo_janitor_workspace/ (git-excluded via .git/info/exclude).
