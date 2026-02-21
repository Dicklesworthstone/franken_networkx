#![forbid(unsafe_code)]

use fnx_runtime::{
    CompatibilityMode, DecisionAction, DecisionRecord, EvidenceLedger, EvidenceTerm,
    decision_theoretic_action, unix_time_ms,
};
use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;
use std::fmt;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct BackendSpec {
    pub name: String,
    pub priority: u32,
    pub supported_features: BTreeSet<String>,
    pub allow_in_strict: bool,
    pub allow_in_hardened: bool,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct DispatchRequest {
    pub operation: String,
    pub requested_backend: Option<String>,
    pub required_features: BTreeSet<String>,
    pub risk_probability: f64,
    pub unknown_incompatible_feature: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct DispatchDecision {
    pub action: DecisionAction,
    pub selected_backend: Option<String>,
    pub mode: CompatibilityMode,
    pub operation: String,
    pub reason: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum DispatchError {
    FailClosed { operation: String, reason: String },
    NoCompatibleBackend { operation: String },
}

impl fmt::Display for DispatchError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::FailClosed { operation, reason } => {
                write!(f, "dispatch for `{operation}` failed closed: {reason}")
            }
            Self::NoCompatibleBackend { operation } => {
                write!(f, "no compatible backend available for `{operation}`")
            }
        }
    }
}

impl std::error::Error for DispatchError {}

#[derive(Debug, Clone)]
pub struct BackendRegistry {
    mode: CompatibilityMode,
    backends: Vec<BackendSpec>,
    ledger: EvidenceLedger,
}

impl BackendRegistry {
    #[must_use]
    pub fn new(mode: CompatibilityMode) -> Self {
        Self {
            mode,
            backends: Vec::new(),
            ledger: EvidenceLedger::new(),
        }
    }

    #[must_use]
    pub fn strict() -> Self {
        Self::new(CompatibilityMode::Strict)
    }

    #[must_use]
    pub fn hardened() -> Self {
        Self::new(CompatibilityMode::Hardened)
    }

    pub fn register_backend(&mut self, backend: BackendSpec) {
        self.backends.push(backend);
        self.backends.sort_by(|a, b| {
            b.priority
                .cmp(&a.priority)
                .then_with(|| a.name.cmp(&b.name))
        });
    }

    #[must_use]
    pub fn evidence_ledger(&self) -> &EvidenceLedger {
        &self.ledger
    }

    pub fn resolve(
        &mut self,
        request: &DispatchRequest,
    ) -> Result<DispatchDecision, DispatchError> {
        let action = decision_theoretic_action(
            self.mode,
            request.risk_probability,
            request.unknown_incompatible_feature,
        );

        if action == DecisionAction::FailClosed {
            self.record_dispatch(request, action, None, "unknown_incompatible_feature");
            return Err(DispatchError::FailClosed {
                operation: request.operation.clone(),
                reason: "unknown incompatible feature in dispatch request".to_owned(),
            });
        }

        let compatible: Vec<&BackendSpec> = self
            .backends
            .iter()
            .filter(|backend| {
                let mode_allowed = match self.mode {
                    CompatibilityMode::Strict => backend.allow_in_strict,
                    CompatibilityMode::Hardened => backend.allow_in_hardened,
                };
                mode_allowed
                    && request
                        .required_features
                        .is_subset(&backend.supported_features)
            })
            .collect();

        if compatible.is_empty() {
            self.record_dispatch(request, action, None, "no_compatible_backend");
            return Err(DispatchError::NoCompatibleBackend {
                operation: request.operation.clone(),
            });
        }

        let selected = if let Some(name) = &request.requested_backend {
            compatible
                .iter()
                .find(|backend| backend.name == *name)
                .copied()
        } else {
            compatible.first().copied()
        };

        let Some(selected) = selected else {
            self.record_dispatch(request, action, None, "requested_backend_unavailable");
            return Err(DispatchError::FailClosed {
                operation: request.operation.clone(),
                reason: "requested backend unavailable under current compatibility mode".to_owned(),
            });
        };

        let selected_name = selected.name.clone();
        self.record_dispatch(request, action, Some(&selected_name), "dispatch_selected");
        Ok(DispatchDecision {
            action,
            selected_backend: Some(selected_name),
            mode: self.mode,
            operation: request.operation.clone(),
            reason: "deterministic backend priority selection".to_owned(),
        })
    }

    fn record_dispatch(
        &mut self,
        request: &DispatchRequest,
        action: DecisionAction,
        selected_backend: Option<&str>,
        reason: &str,
    ) {
        self.ledger.record(DecisionRecord {
            ts_unix_ms: unix_time_ms(),
            operation: format!("dispatch::{}", request.operation),
            mode: self.mode,
            action,
            incompatibility_probability: if request.risk_probability.is_nan() {
                1.0
            } else {
                request.risk_probability.clamp(0.0, 1.0)
            },
            rationale: reason.to_owned(),
            evidence: vec![
                EvidenceTerm {
                    signal: "requested_backend".to_owned(),
                    observed_value: request
                        .requested_backend
                        .clone()
                        .unwrap_or_else(|| "none".to_owned()),
                    log_likelihood_ratio: -1.0,
                },
                EvidenceTerm {
                    signal: "required_feature_count".to_owned(),
                    observed_value: request.required_features.len().to_string(),
                    log_likelihood_ratio: -0.5,
                },
                EvidenceTerm {
                    signal: "selected_backend".to_owned(),
                    observed_value: selected_backend.unwrap_or("none").to_owned(),
                    log_likelihood_ratio: if selected_backend.is_some() {
                        -2.0
                    } else {
                        4.0
                    },
                },
            ],
        });
    }
}

#[cfg(test)]
mod tests {
    use super::{BackendRegistry, BackendSpec, DispatchDecision, DispatchError, DispatchRequest};
    use fnx_runtime::{
        CompatibilityMode, DecisionAction, EvidenceLedger, ForensicsBundleIndex, StructuredTestLog,
        TestKind, TestStatus, canonical_environment_fingerprint,
        structured_test_log_schema_version,
    };
    use std::collections::{BTreeMap, BTreeSet};

    fn set(values: &[&str]) -> BTreeSet<String> {
        values.iter().map(|v| (*v).to_owned()).collect()
    }

    fn register_packet_003_backends(registry: &mut BackendRegistry) {
        registry.register_backend(BackendSpec {
            name: "beta-backend".to_owned(),
            priority: 100,
            supported_features: set(&["dispatch"]),
            allow_in_strict: true,
            allow_in_hardened: true,
        });
        registry.register_backend(BackendSpec {
            name: "alpha-backend".to_owned(),
            priority: 100,
            supported_features: set(&["dispatch", "shortest_path"]),
            allow_in_strict: true,
            allow_in_hardened: true,
        });
    }

    fn resolve_packet_003(
        mode: CompatibilityMode,
        request: &DispatchRequest,
    ) -> (Result<DispatchDecision, DispatchError>, EvidenceLedger) {
        let mut registry = BackendRegistry::new(mode);
        register_packet_003_backends(&mut registry);
        let outcome = registry.resolve(request);
        (outcome, registry.evidence_ledger().clone())
    }

    fn packet_003_forensics_bundle(
        run_id: &str,
        test_id: &str,
        replay_ref: &str,
        bundle_id: &str,
        artifact_refs: Vec<String>,
    ) -> ForensicsBundleIndex {
        ForensicsBundleIndex {
            bundle_id: bundle_id.to_owned(),
            run_id: run_id.to_owned(),
            test_id: test_id.to_owned(),
            bundle_hash_id: "bundle-hash-p2c003".to_owned(),
            captured_unix_ms: 1,
            replay_ref: replay_ref.to_owned(),
            artifact_refs,
            raptorq_sidecar_refs: Vec::new(),
            decode_proof_refs: Vec::new(),
        }
    }

    #[test]
    fn strict_mode_rejects_unknown_incompatible_request() {
        let mut registry = BackendRegistry::strict();
        registry.register_backend(BackendSpec {
            name: "native".to_owned(),
            priority: 100,
            supported_features: set(&["shortest_path"]),
            allow_in_strict: true,
            allow_in_hardened: true,
        });

        let request = DispatchRequest {
            operation: "shortest_path".to_owned(),
            requested_backend: None,
            required_features: set(&["shortest_path"]),
            risk_probability: 0.2,
            unknown_incompatible_feature: true,
        };

        let err = registry
            .resolve(&request)
            .expect_err("strict mode must fail closed");
        assert!(matches!(err, DispatchError::FailClosed { .. }));
    }

    #[test]
    fn hardened_mode_uses_validation_action_for_moderate_risk() {
        let mut registry = BackendRegistry::hardened();
        registry.register_backend(BackendSpec {
            name: "native".to_owned(),
            priority: 100,
            supported_features: set(&["convert"]),
            allow_in_strict: true,
            allow_in_hardened: true,
        });

        let request = DispatchRequest {
            operation: "convert".to_owned(),
            requested_backend: None,
            required_features: set(&["convert"]),
            risk_probability: 0.2,
            unknown_incompatible_feature: false,
        };

        let decision = registry
            .resolve(&request)
            .expect("dispatch should succeed in hardened mode");
        assert_eq!(decision.action, DecisionAction::FullValidate);
        assert_eq!(decision.selected_backend, Some("native".to_owned()));
    }

    #[test]
    fn deterministic_priority_selects_highest_then_name() {
        let mut registry = BackendRegistry::strict();
        registry.register_backend(BackendSpec {
            name: "b-backend".to_owned(),
            priority: 100,
            supported_features: set(&["readwrite"]),
            allow_in_strict: true,
            allow_in_hardened: true,
        });
        registry.register_backend(BackendSpec {
            name: "a-backend".to_owned(),
            priority: 100,
            supported_features: set(&["readwrite"]),
            allow_in_strict: true,
            allow_in_hardened: true,
        });

        let request = DispatchRequest {
            operation: "readwrite".to_owned(),
            requested_backend: None,
            required_features: set(&["readwrite"]),
            risk_probability: 0.01,
            unknown_incompatible_feature: false,
        };

        let decision = registry.resolve(&request).expect("dispatch should succeed");
        assert_eq!(decision.selected_backend, Some("a-backend".to_owned()));
    }

    #[test]
    fn unit_packet_003_contract_asserted() {
        let mut registry = BackendRegistry::strict();
        register_packet_003_backends(&mut registry);

        let request = DispatchRequest {
            operation: "dispatch_contract".to_owned(),
            requested_backend: None,
            required_features: set(&["dispatch"]),
            risk_probability: 0.2,
            unknown_incompatible_feature: false,
        };

        let decision = registry
            .resolve(&request)
            .expect("packet-003 unit contract fixture should dispatch");
        assert_eq!(decision.selected_backend.as_deref(), Some("alpha-backend"));
        assert_eq!(decision.mode, CompatibilityMode::Strict);

        let records = registry.evidence_ledger().records();
        assert_eq!(
            records.len(),
            1,
            "unit dispatch should record a single decision"
        );
        let record = &records[0];
        assert_eq!(record.operation, "dispatch::dispatch_contract");
        assert_eq!(record.mode, CompatibilityMode::Strict);
        assert_eq!(record.action, decision.action);
        assert!(
            record
                .evidence
                .iter()
                .any(|term| term.signal == "selected_backend"
                    && term.observed_value == "alpha-backend"),
            "ledger evidence should contain selected backend"
        );

        let mut environment = BTreeMap::new();
        environment.insert("os".to_owned(), std::env::consts::OS.to_owned());
        environment.insert("arch".to_owned(), std::env::consts::ARCH.to_owned());
        environment.insert("route_id".to_owned(), record.operation.clone());
        environment.insert("backend_name".to_owned(), "alpha-backend".to_owned());
        environment.insert("strict_mode".to_owned(), "true".to_owned());

        let replay_command = "rch exec -- cargo test -p fnx-dispatch unit_packet_003_contract_asserted -- --nocapture";
        let log = StructuredTestLog {
            schema_version: structured_test_log_schema_version().to_owned(),
            run_id: "dispatch-p2c003-unit".to_owned(),
            ts_unix_ms: 1,
            crate_name: "fnx-dispatch".to_owned(),
            suite_id: "unit".to_owned(),
            packet_id: "FNX-P2C-003".to_owned(),
            test_name: "unit_packet_003_contract_asserted".to_owned(),
            test_id: "unit::fnx-p2c-003::contract".to_owned(),
            test_kind: TestKind::Unit,
            mode: CompatibilityMode::Strict,
            fixture_id: Some("dispatch::contract::strict".to_owned()),
            seed: Some(7103),
            env_fingerprint: canonical_environment_fingerprint(&environment),
            environment,
            duration_ms: 5,
            replay_command: replay_command.to_owned(),
            artifact_refs: vec!["artifacts/conformance/latest/structured_logs.jsonl".to_owned()],
            forensic_bundle_id: "forensics::dispatch::unit::contract".to_owned(),
            hash_id: "sha256:dispatch-p2c003-unit".to_owned(),
            status: TestStatus::Passed,
            reason_code: None,
            failure_repro: None,
            e2e_step_traces: Vec::new(),
            forensics_bundle_index: Some(packet_003_forensics_bundle(
                "dispatch-p2c003-unit",
                "unit::fnx-p2c-003::contract",
                replay_command,
                "forensics::dispatch::unit::contract",
                vec!["artifacts/conformance/latest/structured_logs.jsonl".to_owned()],
            )),
        };
        log.validate()
            .expect("unit packet-003 telemetry log should satisfy strict schema");
    }

    #[test]
    fn property_packet_003_invariants() {
        let requested_backends = [
            None,
            Some("alpha-backend".to_owned()),
            Some("beta-backend".to_owned()),
            Some("missing-backend".to_owned()),
        ];
        let dispatch_only = set(&["dispatch"]);
        let feature_sets = [
            dispatch_only.clone(),
            set(&["dispatch", "shortest_path"]),
            set(&["missing_feature"]),
        ];

        for mode in [CompatibilityMode::Strict, CompatibilityMode::Hardened] {
            for risk_probability in [0.0, 0.2, 0.49, 0.8] {
                for unknown_incompatible_feature in [false, true] {
                    for requested_backend in &requested_backends {
                        for required_features in &feature_sets {
                            let request = DispatchRequest {
                                operation: "dispatch_property".to_owned(),
                                requested_backend: requested_backend.clone(),
                                required_features: required_features.clone(),
                                risk_probability,
                                unknown_incompatible_feature,
                            };

                            let (left_result, left_ledger) = resolve_packet_003(mode, &request);
                            let (right_result, right_ledger) = resolve_packet_003(mode, &request);

                            assert_eq!(
                                left_result, right_result,
                                "dispatch replay determinism drifted for mode={mode:?}, risk={risk_probability}, unknown={unknown_incompatible_feature}, requested={requested_backend:?}, required={required_features:?}"
                            );
                            assert_eq!(left_ledger.records().len(), 1);
                            assert_eq!(right_ledger.records().len(), 1);

                            let left_record = &left_ledger.records()[0];
                            let right_record = &right_ledger.records()[0];
                            assert_eq!(left_record.action, right_record.action);
                            assert_eq!(left_record.operation, "dispatch::dispatch_property");
                            assert_eq!(left_record.mode, mode);
                            assert!(
                                left_record
                                    .evidence
                                    .iter()
                                    .any(|term| term.signal == "selected_backend"),
                                "selected backend evidence should be present"
                            );

                            if unknown_incompatible_feature {
                                assert!(
                                    matches!(left_result, Err(DispatchError::FailClosed { .. })),
                                    "unknown incompatible feature must always fail closed"
                                );
                            }

                            if request.requested_backend.is_none()
                                && request.required_features == dispatch_only
                                && !unknown_incompatible_feature
                                && let Ok(decision) = &left_result
                            {
                                assert_eq!(
                                    decision.selected_backend.as_deref(),
                                    Some("alpha-backend"),
                                    "lexical tie-break should remain deterministic"
                                );
                            }
                        }
                    }
                }
            }
        }
    }
}
