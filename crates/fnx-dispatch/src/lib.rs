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
            incompatibility_probability: request.risk_probability.clamp(0.0, 1.0),
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
    use super::{BackendRegistry, BackendSpec, DispatchError, DispatchRequest};
    use fnx_runtime::DecisionAction;
    use std::collections::BTreeSet;

    fn set(values: &[&str]) -> BTreeSet<String> {
        values.iter().map(|v| (*v).to_owned()).collect()
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
}
