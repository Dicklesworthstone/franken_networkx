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

// ---------------------------------------------------------------------------
// Backend Discovery
// ---------------------------------------------------------------------------

/// Describes a backend that can be auto-discovered at runtime.
///
/// Use `discover_standard_backends()` to get the list of all known backends,
/// or implement custom discovery by creating `DiscoveredBackend` instances.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct DiscoveredBackend {
    /// Unique backend identifier
    pub name: String,
    /// Higher priority backends are preferred
    pub priority: u32,
    /// Set of features this backend supports
    pub supported_features: BTreeSet<String>,
    /// Whether this backend is allowed in strict compatibility mode
    pub allow_in_strict: bool,
    /// Whether this backend is allowed in hardened compatibility mode
    pub allow_in_hardened: bool,
    /// Human-readable description of the backend
    pub description: String,
    /// Version string for the backend implementation
    pub version: String,
}

impl DiscoveredBackend {
    /// Convert to a `BackendSpec` for registry registration.
    #[must_use]
    pub fn to_spec(&self) -> BackendSpec {
        BackendSpec {
            name: self.name.clone(),
            priority: self.priority,
            supported_features: self.supported_features.clone(),
            allow_in_strict: self.allow_in_strict,
            allow_in_hardened: self.allow_in_hardened,
        }
    }
}

/// Returns a list of all standard backends known to the FrankenNetworkX runtime.
///
/// This function provides auto-discovery of available backend implementations.
/// Call this at application startup to populate a `BackendRegistry` with all
/// available backends without manually specifying each one.
///
/// # Example
///
/// ```
/// use fnx_dispatch::{BackendRegistry, discover_standard_backends};
/// use fnx_runtime::CompatibilityMode;
///
/// let mut registry = BackendRegistry::new(CompatibilityMode::Strict);
/// for backend in discover_standard_backends() {
///     registry.register_backend(backend.to_spec());
/// }
/// ```
#[must_use]
pub fn discover_standard_backends() -> Vec<DiscoveredBackend> {
    vec![
        DiscoveredBackend {
            name: "native".to_owned(),
            priority: 100,
            supported_features: [
                "shortest_path",
                "shortest_path_weighted",
                "connected_components",
                "strongly_connected_components",
                "centrality",
                "clustering",
                "flow",
                "matching",
                "mst",
                "traversal",
                "readwrite",
                "convert",
            ]
            .into_iter()
            .map(str::to_owned)
            .collect(),
            allow_in_strict: true,
            allow_in_hardened: true,
            description: "Native Rust implementation of NetworkX algorithms".to_owned(),
            version: env!("CARGO_PKG_VERSION").to_owned(),
        },
        DiscoveredBackend {
            name: "compat_probe".to_owned(),
            priority: 50,
            supported_features: ["shortest_path", "shortest_path_weighted"]
                .into_iter()
                .map(str::to_owned)
                .collect(),
            allow_in_strict: true,
            allow_in_hardened: true,
            description: "Compatibility probing backend for conformance testing".to_owned(),
            version: env!("CARGO_PKG_VERSION").to_owned(),
        },
    ]
}

/// Returns a report of all discovered backends with their capabilities.
///
/// Useful for debugging and diagnostics to see what backends are available.
#[must_use]
pub fn discovery_report() -> DiscoveryReport {
    let backends = discover_standard_backends();
    let mut all_features: BTreeSet<String> = BTreeSet::new();
    for backend in &backends {
        all_features.extend(backend.supported_features.iter().cloned());
    }

    DiscoveryReport {
        backend_count: backends.len(),
        backends,
        all_features,
        discovery_version: "1.0.0".to_owned(),
    }
}

/// Summary report of backend discovery results.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct DiscoveryReport {
    pub backend_count: usize,
    pub backends: Vec<DiscoveredBackend>,
    pub all_features: BTreeSet<String>,
    pub discovery_version: String,
}

// ---------------------------------------------------------------------------
// Coverage Measurement
// ---------------------------------------------------------------------------

/// Tracks which dispatch operations have been exercised.
///
/// Use this to measure test coverage of dispatch paths and identify
/// gaps in algorithm usage.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct DispatchCoverage {
    /// Operations that were successfully dispatched
    pub dispatched_operations: BTreeSet<String>,
    /// Features that were requested during dispatch
    pub requested_features: BTreeSet<String>,
    /// Backends that handled at least one dispatch
    pub used_backends: BTreeSet<String>,
    /// Operations that failed to dispatch
    pub failed_operations: BTreeSet<String>,
    /// Total successful dispatch count
    pub success_count: usize,
    /// Total failed dispatch count
    pub failure_count: usize,
}

impl DispatchCoverage {
    /// Create a new empty coverage tracker.
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    /// Record a successful dispatch.
    pub fn record_success(&mut self, operation: &str, backend: &str, features: &BTreeSet<String>) {
        self.dispatched_operations.insert(operation.to_owned());
        self.used_backends.insert(backend.to_owned());
        self.requested_features.extend(features.iter().cloned());
        self.success_count += 1;
    }

    /// Record a failed dispatch.
    pub fn record_failure(&mut self, operation: &str, features: &BTreeSet<String>) {
        self.failed_operations.insert(operation.to_owned());
        self.requested_features.extend(features.iter().cloned());
        self.failure_count += 1;
    }

    /// Merge another coverage report into this one.
    pub fn merge(&mut self, other: &Self) {
        self.dispatched_operations
            .extend(other.dispatched_operations.iter().cloned());
        self.requested_features
            .extend(other.requested_features.iter().cloned());
        self.used_backends
            .extend(other.used_backends.iter().cloned());
        self.failed_operations
            .extend(other.failed_operations.iter().cloned());
        self.success_count += other.success_count;
        self.failure_count += other.failure_count;
    }

    /// Generate a gap report comparing coverage against available features.
    #[must_use]
    pub fn gap_report(&self, discovery: &DiscoveryReport) -> CoverageGapReport {
        let available_features = &discovery.all_features;
        let available_backends: BTreeSet<String> = discovery
            .backends
            .iter()
            .map(|b| b.name.clone())
            .collect();

        let untested_features: BTreeSet<String> = available_features
            .difference(&self.requested_features)
            .cloned()
            .collect();

        let unused_backends: BTreeSet<String> = available_backends
            .difference(&self.used_backends)
            .cloned()
            .collect();

        let feature_coverage_pct = if available_features.is_empty() {
            100.0
        } else {
            (self.requested_features.len() as f64 / available_features.len() as f64) * 100.0
        };

        let backend_coverage_pct = if available_backends.is_empty() {
            100.0
        } else {
            (self.used_backends.len() as f64 / available_backends.len() as f64) * 100.0
        };

        CoverageGapReport {
            untested_features,
            unused_backends,
            tested_features: self.requested_features.clone(),
            used_backends: self.used_backends.clone(),
            failed_operations: self.failed_operations.clone(),
            feature_coverage_pct,
            backend_coverage_pct,
            total_dispatches: self.success_count + self.failure_count,
            success_rate_pct: if self.success_count + self.failure_count == 0 {
                100.0
            } else {
                (self.success_count as f64
                    / (self.success_count + self.failure_count) as f64)
                    * 100.0
            },
        }
    }
}

/// Report identifying gaps in dispatch coverage.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct CoverageGapReport {
    /// Features available but never requested
    pub untested_features: BTreeSet<String>,
    /// Backends registered but never used
    pub unused_backends: BTreeSet<String>,
    /// Features that were tested
    pub tested_features: BTreeSet<String>,
    /// Backends that were used
    pub used_backends: BTreeSet<String>,
    /// Operations that failed to dispatch
    pub failed_operations: BTreeSet<String>,
    /// Percentage of available features tested (0-100)
    pub feature_coverage_pct: f64,
    /// Percentage of available backends used (0-100)
    pub backend_coverage_pct: f64,
    /// Total number of dispatch attempts
    pub total_dispatches: usize,
    /// Percentage of successful dispatches (0-100)
    pub success_rate_pct: f64,
}

impl CoverageGapReport {
    /// Returns true if all features have been tested.
    #[must_use]
    pub fn is_feature_complete(&self) -> bool {
        self.untested_features.is_empty()
    }

    /// Returns true if all backends have been used.
    #[must_use]
    pub fn is_backend_complete(&self) -> bool {
        self.unused_backends.is_empty()
    }

    /// Returns true if there were no dispatch failures.
    #[must_use]
    pub fn is_failure_free(&self) -> bool {
        self.failed_operations.is_empty()
    }
}

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

    /// Create a new registry with all auto-discovered backends pre-registered.
    ///
    /// This is the recommended way to create a registry for production use,
    /// as it automatically includes all available backend implementations.
    ///
    /// # Example
    ///
    /// ```
    /// use fnx_dispatch::BackendRegistry;
    /// use fnx_runtime::CompatibilityMode;
    ///
    /// let registry = BackendRegistry::with_discovered_backends(CompatibilityMode::Strict);
    /// // Registry now contains all standard backends
    /// ```
    #[must_use]
    pub fn with_discovered_backends(mode: CompatibilityMode) -> Self {
        let mut registry = Self::new(mode);
        for backend in discover_standard_backends() {
            registry.register_backend(backend.to_spec());
        }
        registry
    }

    /// Returns a list of all registered backends.
    #[must_use]
    pub fn backends(&self) -> &[BackendSpec] {
        &self.backends
    }

    /// Returns the current compatibility mode.
    #[must_use]
    pub fn mode(&self) -> CompatibilityMode {
        self.mode
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
            let (reason, error_reason) = if request.unknown_incompatible_feature {
                (
                    "unknown_incompatible_feature",
                    "unknown incompatible feature in dispatch request",
                )
            } else if request.risk_probability.is_nan() {
                ("risk_probability_nan", "risk probability is NaN")
            } else {
                (
                    "risk_probability_too_high",
                    "risk probability exceeds allowed threshold",
                )
            };
            self.record_dispatch(request, action, None, reason);
            return Err(DispatchError::FailClosed {
                operation: request.operation.clone(),
                reason: error_reason.to_owned(),
            });
        }

        let compatible_backend = if let Some(name) = &request.requested_backend {
            self.backends.iter().find(|backend| {
                backend.name == *name
                    && (match self.mode {
                        CompatibilityMode::Strict => backend.allow_in_strict,
                        CompatibilityMode::Hardened => backend.allow_in_hardened,
                    })
                    && request
                        .required_features
                        .is_subset(&backend.supported_features)
            })
        } else {
            self.backends.iter().find(|backend| {
                (match self.mode {
                    CompatibilityMode::Strict => backend.allow_in_strict,
                    CompatibilityMode::Hardened => backend.allow_in_hardened,
                }) && request
                    .required_features
                    .is_subset(&backend.supported_features)
            })
        };

        let Some(selected) = compatible_backend else {
            let (reason, error) = if request.requested_backend.is_some() {
                (
                    "requested_backend_unavailable",
                    DispatchError::FailClosed {
                        operation: request.operation.clone(),
                        reason: "requested backend unavailable under current compatibility mode"
                            .to_owned(),
                    },
                )
            } else {
                (
                    "no_compatible_backend",
                    DispatchError::NoCompatibleBackend {
                        operation: request.operation.clone(),
                    },
                )
            };
            self.record_dispatch(request, action, None, reason);
            return Err(error);
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
                        .as_deref()
                        .unwrap_or("none")
                        .to_owned(),
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
    fn strict_mode_fail_closed_reason_reports_risk_probability() {
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
            risk_probability: 0.99,
            unknown_incompatible_feature: false,
        };

        let err = registry
            .resolve(&request)
            .expect_err("strict mode must fail closed for high risk");
        assert!(matches!(
            err,
            DispatchError::FailClosed { ref reason, .. }
                if reason == "risk probability exceeds allowed threshold"
        ));
    }

    #[test]
    fn strict_mode_fail_closed_reason_reports_nan_probability() {
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
            risk_probability: f64::NAN,
            unknown_incompatible_feature: false,
        };

        let err = registry
            .resolve(&request)
            .expect_err("strict mode must fail closed for NaN risk");
        assert!(matches!(
            err,
            DispatchError::FailClosed { ref reason, .. }
                if reason == "risk probability is NaN"
        ));
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
            risk_probability: 0.3,
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

    // -----------------------------------------------------------------------
    // Auto-discovery tests
    // -----------------------------------------------------------------------

    #[test]
    fn discover_standard_backends_returns_native() {
        let backends = super::discover_standard_backends();
        assert!(!backends.is_empty(), "should discover at least one backend");
        assert!(
            backends.iter().any(|b| b.name == "native"),
            "should include native backend"
        );
    }

    #[test]
    fn discover_standard_backends_native_has_expected_features() {
        let backends = super::discover_standard_backends();
        let native = backends
            .iter()
            .find(|b| b.name == "native")
            .expect("native backend should exist");

        assert!(native.supported_features.contains("shortest_path"));
        assert!(native.supported_features.contains("connected_components"));
        assert!(native.supported_features.contains("centrality"));
        assert!(native.allow_in_strict);
        assert!(native.allow_in_hardened);
        assert_eq!(native.priority, 100);
    }

    #[test]
    fn with_discovered_backends_registers_all_standard() {
        let registry = BackendRegistry::with_discovered_backends(CompatibilityMode::Strict);
        let standard = super::discover_standard_backends();

        assert_eq!(
            registry.backends().len(),
            standard.len(),
            "registry should have all discovered backends"
        );

        for backend in &standard {
            assert!(
                registry.backends().iter().any(|b| b.name == backend.name),
                "registry should contain {}",
                backend.name
            );
        }
    }

    #[test]
    fn with_discovered_backends_can_dispatch() {
        let mut registry = BackendRegistry::with_discovered_backends(CompatibilityMode::Strict);

        let request = DispatchRequest {
            operation: "shortest_path".to_owned(),
            requested_backend: None,
            required_features: set(&["shortest_path"]),
            risk_probability: 0.01,
            unknown_incompatible_feature: false,
        };

        let decision = registry
            .resolve(&request)
            .expect("dispatch should succeed with discovered backends");
        assert_eq!(decision.selected_backend.as_deref(), Some("native"));
    }

    #[test]
    fn discovery_report_includes_all_features() {
        let report = super::discovery_report();
        assert!(report.backend_count > 0);
        assert!(!report.all_features.is_empty());
        assert!(report.all_features.contains("shortest_path"));
        assert_eq!(report.discovery_version, "1.0.0");
    }

    #[test]
    fn discovered_backend_to_spec_roundtrip() {
        let discovered = super::DiscoveredBackend {
            name: "test".to_owned(),
            priority: 75,
            supported_features: set(&["feature_a", "feature_b"]),
            allow_in_strict: true,
            allow_in_hardened: false,
            description: "Test backend".to_owned(),
            version: "0.0.1".to_owned(),
        };

        let spec = discovered.to_spec();
        assert_eq!(spec.name, "test");
        assert_eq!(spec.priority, 75);
        assert_eq!(spec.supported_features, set(&["feature_a", "feature_b"]));
        assert!(spec.allow_in_strict);
        assert!(!spec.allow_in_hardened);
    }

    // -----------------------------------------------------------------------
    // Coverage measurement tests
    // -----------------------------------------------------------------------

    #[test]
    fn coverage_tracks_successful_dispatches() {
        let mut coverage = super::DispatchCoverage::new();

        coverage.record_success("shortest_path", "native", &set(&["shortest_path"]));
        coverage.record_success("centrality", "native", &set(&["centrality"]));

        assert_eq!(coverage.success_count, 2);
        assert_eq!(coverage.failure_count, 0);
        assert!(coverage.dispatched_operations.contains("shortest_path"));
        assert!(coverage.dispatched_operations.contains("centrality"));
        assert!(coverage.used_backends.contains("native"));
        assert!(coverage.requested_features.contains("shortest_path"));
        assert!(coverage.requested_features.contains("centrality"));
    }

    #[test]
    fn coverage_tracks_failed_dispatches() {
        let mut coverage = super::DispatchCoverage::new();

        coverage.record_failure("unknown_op", &set(&["unknown_feature"]));

        assert_eq!(coverage.success_count, 0);
        assert_eq!(coverage.failure_count, 1);
        assert!(coverage.failed_operations.contains("unknown_op"));
        assert!(coverage.requested_features.contains("unknown_feature"));
    }

    #[test]
    fn coverage_merge_combines_reports() {
        let mut coverage1 = super::DispatchCoverage::new();
        coverage1.record_success("op1", "backend1", &set(&["feature1"]));

        let mut coverage2 = super::DispatchCoverage::new();
        coverage2.record_success("op2", "backend2", &set(&["feature2"]));

        coverage1.merge(&coverage2);

        assert_eq!(coverage1.success_count, 2);
        assert!(coverage1.dispatched_operations.contains("op1"));
        assert!(coverage1.dispatched_operations.contains("op2"));
        assert!(coverage1.used_backends.contains("backend1"));
        assert!(coverage1.used_backends.contains("backend2"));
    }

    #[test]
    fn gap_report_identifies_untested_features() {
        let mut coverage = super::DispatchCoverage::new();
        coverage.record_success("shortest_path", "native", &set(&["shortest_path"]));

        let discovery = super::discovery_report();
        let gap = coverage.gap_report(&discovery);

        // We only tested shortest_path, so other features should be untested
        assert!(!gap.untested_features.is_empty());
        assert!(gap.tested_features.contains("shortest_path"));
        assert!(!gap.untested_features.contains("shortest_path"));
        assert!(gap.used_backends.contains("native"));
    }

    #[test]
    fn gap_report_calculates_coverage_percentages() {
        let mut coverage = super::DispatchCoverage::new();
        let discovery = super::discovery_report();

        // Test half the features
        let half_features: Vec<_> = discovery
            .all_features
            .iter()
            .take(discovery.all_features.len() / 2)
            .cloned()
            .collect();

        for feature in &half_features {
            coverage.record_success(feature, "native", &set(&[feature.as_str()]));
        }

        let gap = coverage.gap_report(&discovery);
        assert!(gap.feature_coverage_pct > 0.0);
        assert!(gap.feature_coverage_pct <= 100.0);
        assert!(gap.backend_coverage_pct > 0.0);
    }

    #[test]
    fn gap_report_success_rate_calculation() {
        let mut coverage = super::DispatchCoverage::new();
        coverage.record_success("op1", "native", &set(&["f1"]));
        coverage.record_success("op2", "native", &set(&["f2"]));
        coverage.record_failure("op3", &set(&["f3"]));

        let gap = coverage.gap_report(&super::discovery_report());

        assert_eq!(gap.total_dispatches, 3);
        // 2 successes out of 3 = 66.67%
        assert!((gap.success_rate_pct - 66.67).abs() < 1.0);
    }

    #[test]
    fn gap_report_completeness_checks() {
        let mut coverage = super::DispatchCoverage::new();
        let discovery = super::discovery_report();

        // Test all features and use all backends
        for feature in &discovery.all_features {
            coverage.record_success(feature, "native", &set(&[feature.as_str()]));
        }
        for backend in &discovery.backends {
            coverage.record_success("dummy", &backend.name, &BTreeSet::new());
        }

        let gap = coverage.gap_report(&discovery);
        assert!(gap.is_feature_complete());
        assert!(gap.is_backend_complete());
        assert!(gap.is_failure_free());
    }
}
