# Security Policy

## Supported Versions

FrankenNetworkX supports the following versions for security updates.

| Version | Supported          |
| ------- | ------------------ |
| 1.x.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it via GitHub Security Advisories or email the maintainers directly. Do not file a public issue for security-related matters.

We aim to acknowledge reports within 48 hours and provide a timeline for remediation.

### Safe by Design
As a Rust-backed project, FrankenNetworkX avoids many memory-safety issues inherent to C/C++ extensions. However, algorithmic complexity attacks (e.g., hash collisions or adversarial graph generation) are within scope for security reports if they bypass the Hardened Mode safeguards.

## Threat Model Notes

FrankenNetworkX's security posture is not just "memory safe." The main in-scope threat classes are:

- malformed graph ingestion
- attribute confusion and type-coercion drift
- algorithmic denial on adversarial graphs
- provenance or evidence integrity drift
- policy-enforcement and backend-routing ambiguity

The project-wide rule is consistent across subsystems: preserve NetworkX-observable behavior in `strict` mode, allow only bounded and auditable recovery in `hardened` mode, and fail closed on unknown incompatible features.

### Major Subsystems

| Subsystem | Rust owner(s) | Primary threats | Security posture | Primary evidence |
| --- | --- | --- | --- | --- |
| CGSE semantics | `fnx-cgse`, `fnx-runtime`, `fnx-algorithms` | Tie-break drift, policy bypass, witness hash mismatch | Fail closed on policy or witness drift; hardened deviations must stay allowlist-bound and replayable | `artifacts/cgse/v1/cgse_semantics_threat_model_v1.md` |
| Graph storage | `fnx-classes` | Mutable identity drift, multi-edge key reuse mistakes, partial mutation state | Deterministic mutation semantics; reject incompatible identity inputs instead of repairing them heuristically | `EXISTING_NETWORKX_STRUCTURE.md` sections 18-19 |
| Graph views | `fnx-views` | Stale cache reads, live-view mutation during iteration, projection drift | Revision-gated refresh or fail-closed invalidation; never serve silently stale cached views | `EXISTING_NETWORKX_STRUCTURE.md` section 17.2 |
| Compatibility dispatch | `fnx-dispatch`, `fnx-runtime` | Backend-route ambiguity, unsupported conversion paths, config drift | Deterministic routing with explicit decision records; fail closed when no compatible backend satisfies the request | `artifacts/docs/v1/doc_pass04_execution_path_tracing_v1.md` (`dispatch_resolution_runtime`) |
| Conversion ingest | `fnx-convert` | Malformed payload shape, precedence drift, attribute confusion | Strict mode fail-closes; hardened mode may only apply bounded row-local recovery with deterministic warnings | `artifacts/docs/v1/doc_pass04_execution_path_tracing_v1.md` (`conversion_payload_ingest`) |
| I/O serialization | `fnx-readwrite` | Delimiter ambiguity, XML/JSON type coercion, warning-order drift | Preserve deterministic parse and warning ordering; fail closed on unknown incompatible metadata | `artifacts/docs/v1/doc_pass04_execution_path_tracing_v1.md` (`readwrite_serialization_roundtrip`) |
| Algorithm engine | `fnx-algorithms` | Algorithmic denial, tie-break drift, endpoint validation edge cases | Preserve observable NetworkX contracts first; complexity witness and parity evidence are part of the security boundary | `artifacts/docs/v1/doc_pass04_execution_path_tracing_v1.md` (`algorithm_execution_bfs_centrality`) |
| Graph generators | `fnx-generators` | Adversarial parameter combinations, seed instability, duplicate-container semantic drift | Deterministic seeded generation and fail-closed validation for incompatible parameterizations | `artifacts/docs/v1/doc_pass02_symbol_api_census_v1.json` (`graph-generators`) |
| Runtime policy | `fnx-runtime` | Strict/hardened mode drift, malformed runtime config, unlogged recovery decisions | `CompatibilityMode` and `DecisionAction` must stay replayable and explicit; unknown incompatible features remain fail-closed in both modes | `artifacts/docs/v1/doc_pass02_symbol_api_census_v1.json` (`runtime-policy`) |
| Python bindings and public API | `fnx-python`, `python/franken_networkx/` | Exception-mapping drift, attribute coercion drift, thread-safety regressions | Preserve NetworkX-visible exceptions and thread behavior; treat Python-visible parity drift as a security-relevant compatibility failure | `tests/python/test_error_messages.py`, `tests/python/test_thread_safety.py` |
| Conformance harness | `fnx-conformance` | Stale fixtures, provenance spoofing, replay mismatch, false evidence freshness | Provenance-stamped reports, deterministic replay commands, and freshness gates are required before trusting evidence | `README.md` conformance policy, `artifacts/conformance/v1/ci_gate_topology_v1.json` |
| Durability and repair | `fnx-durability` | Corrupted sidecars, decode beyond published recovery bounds, silent scrub drift | Scrub before trust, emit decode proofs on recovery, and fail closed when recovery evidence is incomplete | `artifacts/phase2c/README.md`, `artifacts/phase2c/security/v1/security_compatibility_threat_matrix_v1.json` |

### Cross-Cutting Requirements

- Unknown incompatible features fail closed in both modes.
- Hardened recovery is acceptable only when the recovery is bounded, deterministic, and auditable.
- Security-sensitive behavior changes require matching evidence updates, not just code changes.
- Parser, dispatch, and algorithm surfaces are all in scope for adversarial testing; "it only affects compatibility" is not treated as a security exemption.
