# Risk Note — Track A: Process & Hygiene Reset

## Risk Surface
- parser/ingestion: N/A (no code changes to parsers)
- algorithmic denial vectors: N/A (no algorithm changes)
- **file deletion blast radius**: deleting 100+ files risks losing agent-generated test cases that exercise unique edge cases not covered by the canonical test suite
- **gitignore false positives**: overly broad patterns could exclude legitimate files from tracking

## Failure Modes
- fail-closed triggers: deleted files contained unique test coverage → parity gaps silently reappear
- degraded-mode triggers: gitignore blocks a build artifact needed for CI → CI breaks

## Mitigations
- controls: A1.0 triage of error dumps before deletion; A3 root-test salvage diff comparing root tests vs canonical suite coverage; user sign-off per AGENTS.md Rule 1
- tests: full pytest suite (1394 passed) run before and after cleanup; cargo check clean before and after

## Residual Risk
- unresolved risks: some root-level test scripts may have tested behaviors not covered by named parity tests; however, all were trivial print-and-compare scripts (100-600 bytes) without assertions
- follow-up actions: if a parity regression appears in a future run, check git history for deleted root tests that may have exercised the failing behavior
