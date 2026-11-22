# Critical graph functionality validation — 2026-11-22

This session implemented standard node-link JSON file ingestion, exact stochastic
normalization and complete weighted spanning-tree count domains. The source base
was `e4e9523e3fd6ec0143e968923cab0ff352356e18`. The two Python algorithm units were
published directly to main as `e14569bf369928cb2301cecbeabc30b9e1c667c9` and
`18814733f6153f59325333ea1c9796f7279157b6`.

## Executed evidence

| DSR run | Scope | Result |
| --- | --- | --- |
| `20261122T100333-ZI127YPY` | Released 0.4.1 baseline, 142 selected new Python cases | 63 failures, 79 passes: spanning counts 46/66; stochastic normalization 17/13 |
| `20261122T101126-GTOD1n70` | Frozen candidate Python with released 0.4.1 native extension | Complete count module: 405 passed, 26 existing skips; complete operator module: 320 passed |
| `20261122T101950-6Eu8wG54` | Final changed Rust reader source | Six new native tests passed; reader compile check and changed-package formatting passed |
| `20261122T102434-00gAH8oq` | Fresh extension built from the frozen current candidate | All 119 new JSON file cases passed; neighboring operator/count/node-link modules: 740 passed, 26 existing skips |

The final build used real DSR, the repository's pinned nightly-2026-08-31
toolchain, locked dependencies, one Cargo job, `-Z threads=1`, no incremental
compilation and the development profile without debug symbols. Before executing
the fresh wheel, 155 Python source/stub files were compared with the candidate.
The final binary was not the installed release artifact:

- Fresh wheel SHA-256: `f131a8267b9d09019c22bf3bbdb312ef9388584bf024e16accc3106ce3b30def`.
- Fresh extension SHA-256: `f53ceef9acca47d5f28a5232913a5a01195afe2d5e396eafb1c506d607ae986a`.
- Released 0.4.1 extension SHA-256: `9314ccf170b8a43ca54f2c77822cd26012e5ba6b121cc314386bfbebbf34e386`.

All Python runs used the repository's guarded runner with a 512 MB resident
memory ceiling, a 2 GiB virtual-memory limit and bounded timeouts. The broad
canonical nine-check registry, platform release matrix and performance gates
were not run. This development wheel is functional engineering evidence only;
it is not a release artifact or performance result.

## Earlier failures and static review

The initial full-native attempt failed: the whole-workspace formatter reported
preexisting simplex formatting and four new formatting differences; compiler
processes were killed by SIGKILL in regex-syntax, fnx-python and fnx-algorithms.
Only the new formatting differences were corrected. A scoped reader run and a
later serial full-extension build then succeeded. Those earlier failures remain
recorded in `initial_native_attempt_receipt.json`.

UBS scanned five algorithm files but retained partial Python semantic coverage.
Its 13 critical constant-time-comparison findings were graph-record equality
assertions, not secrets. Changed-code type warnings enforce native admission.
The JSON mixed scan covered four files with zero criticals and partial Python
analysis. A separate full Rust scan covered both changed Rust files with zero
criticals and completed static analysis; its changed-line warnings were test
assertions and diagnostic-string allocations. Cargo phases were reserved for
DSR. The initial changed-regions helper omitted brace-containing Rust definitions,
so the full-file Rust scan was required. No findings were suppressed and partial
Python analysis is not represented as a clean gate.

The two saved validation helpers were also scanned. Their one critical archive
extraction heuristic was reviewed: staging uses the newly built local wheel,
rejects absolute and parent-traversal member paths before extraction, and creates
a new destination directory. The finding does not account for those checks;
it was retained without suppression or changes to the executed script.

Receipts retain the original execution paths and exact source/configuration
hashes. Saved check configurations and execution logs accompany the receipts.
No release or fresh full-canonical qualification bead was closed.
