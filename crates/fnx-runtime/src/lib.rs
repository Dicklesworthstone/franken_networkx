#![forbid(unsafe_code)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum CompatibilityMode {
    Strict,
    Hardened,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum DecisionAction {
    Allow,
    FullValidate,
    FailClosed,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum TestKind {
    Unit,
    Property,
    Differential,
    E2e,
    Fuzz,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum TestStatus {
    Passed,
    Failed,
    Skipped,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct FailureReproData {
    pub failure_message: String,
    pub reproduction_command: String,
    pub expected_behavior: String,
    pub observed_behavior: String,
    pub seed: Option<u64>,
    pub fixture_id: Option<String>,
    pub artifact_hash_id: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct StructuredTestLog {
    pub schema_version: String,
    pub ts_unix_ms: u128,
    pub crate_name: String,
    pub packet_id: String,
    pub test_name: String,
    pub test_kind: TestKind,
    pub mode: CompatibilityMode,
    pub fixture_id: Option<String>,
    pub seed: Option<u64>,
    pub environment: BTreeMap<String, String>,
    pub artifact_refs: Vec<String>,
    pub hash_id: String,
    pub status: TestStatus,
    pub failure_repro: Option<FailureReproData>,
}

impl StructuredTestLog {
    pub fn validate(&self) -> Result<(), String> {
        if self.schema_version.trim().is_empty() {
            return Err("schema_version must be non-empty".to_owned());
        }
        if self.crate_name.trim().is_empty() {
            return Err("crate_name must be non-empty".to_owned());
        }
        if self.packet_id.trim().is_empty() {
            return Err("packet_id must be non-empty".to_owned());
        }
        if self.test_name.trim().is_empty() {
            return Err("test_name must be non-empty".to_owned());
        }
        if self.hash_id.trim().is_empty() {
            return Err("hash_id must be non-empty".to_owned());
        }
        if self.environment.is_empty() {
            return Err("environment must include at least one key".to_owned());
        }
        if self.artifact_refs.is_empty() {
            return Err("artifact_refs must include at least one artifact path/ref".to_owned());
        }

        match self.status {
            TestStatus::Failed => {
                let Some(failure) = &self.failure_repro else {
                    return Err("failure_repro is required when status=failed".to_owned());
                };
                if failure.failure_message.trim().is_empty() {
                    return Err("failure_message must be non-empty for failed status".to_owned());
                }
                if failure.reproduction_command.trim().is_empty() {
                    return Err(
                        "reproduction_command must be non-empty for failed status".to_owned()
                    );
                }
                if failure.seed.is_none() && failure.fixture_id.is_none() {
                    return Err(
                        "failed status requires seed or fixture_id for reproducibility".to_owned(),
                    );
                }
            }
            TestStatus::Passed | TestStatus::Skipped => {
                if self.failure_repro.is_some() {
                    return Err("failure_repro must be omitted unless status=failed".to_owned());
                }
            }
        }

        Ok(())
    }

    pub fn to_json_pretty(&self) -> Result<String, serde_json::Error> {
        serde_json::to_string_pretty(self)
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct EvidenceTerm {
    pub signal: String,
    pub observed_value: String,
    pub log_likelihood_ratio: f64,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct DecisionRecord {
    pub ts_unix_ms: u128,
    pub operation: String,
    pub mode: CompatibilityMode,
    pub action: DecisionAction,
    pub incompatibility_probability: f64,
    pub rationale: String,
    pub evidence: Vec<EvidenceTerm>,
}

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct EvidenceLedger {
    records: Vec<DecisionRecord>,
}

impl EvidenceLedger {
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    pub fn record(&mut self, decision: DecisionRecord) {
        self.records.push(decision);
    }

    #[must_use]
    pub fn records(&self) -> &[DecisionRecord] {
        &self.records
    }

    #[must_use]
    pub fn is_empty(&self) -> bool {
        self.records.is_empty()
    }

    pub fn to_json_pretty(&self) -> Result<String, serde_json::Error> {
        serde_json::to_string_pretty(self)
    }
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct LossMatrix {
    /// False allow: we allowed an actually incompatible operation.
    pub allow_false_negative: f64,
    /// Validation cost regardless of compatibility.
    pub validate_cost: f64,
    /// False reject: we rejected a compatible operation.
    pub reject_false_positive: f64,
}

impl LossMatrix {
    #[must_use]
    pub const fn strict_default() -> Self {
        Self {
            allow_false_negative: 100.0,
            validate_cost: 4.0,
            reject_false_positive: 20.0,
        }
    }

    #[must_use]
    pub const fn hardened_default() -> Self {
        Self {
            allow_false_negative: 120.0,
            validate_cost: 5.0,
            reject_false_positive: 30.0,
        }
    }
}

/// Decision-theoretic selector used by runtime guards.
///
/// We choose `argmin_a E[L(a, state)]` with:
/// - `p`: estimated incompatibility probability
/// - states: `{compatible, incompatible}`
/// - actions: `{allow, full_validate, fail_closed}`
#[must_use]
pub fn decision_theoretic_action(
    mode: CompatibilityMode,
    incompatibility_probability: f64,
    unknown_incompatible_feature: bool,
) -> DecisionAction {
    if unknown_incompatible_feature {
        return DecisionAction::FailClosed;
    }

    let clamped = incompatibility_probability.clamp(0.0, 1.0);
    let loss = match mode {
        CompatibilityMode::Strict => LossMatrix::strict_default(),
        CompatibilityMode::Hardened => LossMatrix::hardened_default(),
    };

    let allow_loss = clamped * loss.allow_false_negative;
    let validate_loss = loss.validate_cost;
    let fail_closed_loss = (1.0 - clamped) * loss.reject_false_positive;

    if fail_closed_loss <= allow_loss && fail_closed_loss <= validate_loss {
        DecisionAction::FailClosed
    } else if validate_loss <= allow_loss {
        DecisionAction::FullValidate
    } else {
        DecisionAction::Allow
    }
}

#[must_use]
pub fn unix_time_ms() -> u128 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or(Duration::from_millis(0))
        .as_millis()
}

#[cfg(feature = "asupersync-integration")]
pub mod asupersync_bridge {
    /// Compile-time marker proving asupersync is wired into this crate.
    #[must_use]
    pub fn integration_marker() -> &'static str {
        let _ = core::any::type_name::<asupersync::Cx>();
        "asupersync-integration-enabled"
    }
}

#[cfg(feature = "ftui-integration")]
pub mod ftui_bridge {
    /// Compile-time marker proving FrankenTUI types are available.
    #[must_use]
    pub fn integration_marker() -> &'static str {
        let _ = core::any::type_name::<ftui::Theme>();
        "ftui-integration-enabled"
    }
}

#[cfg(test)]
mod tests {
    use super::{
        CompatibilityMode, DecisionAction, EvidenceLedger, FailureReproData, StructuredTestLog,
        TestKind, TestStatus, decision_theoretic_action,
    };
    use std::collections::BTreeMap;

    #[test]
    fn strict_mode_prefers_validation_for_uncertain_inputs() {
        let action = decision_theoretic_action(CompatibilityMode::Strict, 0.2, false);
        assert_eq!(action, DecisionAction::FullValidate);
    }

    #[test]
    fn hardened_mode_fails_closed_for_high_risk_inputs() {
        let action = decision_theoretic_action(CompatibilityMode::Hardened, 0.9, false);
        assert_eq!(action, DecisionAction::FailClosed);
    }

    #[test]
    fn both_modes_fail_closed_for_unknown_incompatible_features() {
        let strict = decision_theoretic_action(CompatibilityMode::Strict, 0.0, true);
        let hardened = decision_theoretic_action(CompatibilityMode::Hardened, 0.0, true);
        assert_eq!(strict, DecisionAction::FailClosed);
        assert_eq!(hardened, DecisionAction::FailClosed);
    }

    #[test]
    fn ledger_serializes_to_json() {
        let ledger = EvidenceLedger::new();
        let json = ledger
            .to_json_pretty()
            .expect("ledger json should serialize");
        assert!(json.contains("records"));
    }

    #[test]
    fn structured_test_log_validates_passed_record() {
        let mut env = BTreeMap::new();
        env.insert("os".to_owned(), "linux".to_owned());

        let log = StructuredTestLog {
            schema_version: "1.0.0".to_owned(),
            ts_unix_ms: 1,
            crate_name: "fnx-runtime".to_owned(),
            packet_id: "FNX-P2C-FOUNDATION".to_owned(),
            test_name: "ledger_serializes_to_json".to_owned(),
            test_kind: TestKind::Unit,
            mode: CompatibilityMode::Strict,
            fixture_id: None,
            seed: Some(7),
            environment: env,
            artifact_refs: vec!["artifacts/conformance/latest/smoke_report.json".to_owned()],
            hash_id: "sha256:abc123".to_owned(),
            status: TestStatus::Passed,
            failure_repro: None,
        };

        assert!(log.validate().is_ok());
        let json = log.to_json_pretty().expect("log should serialize");
        assert!(json.contains("ledger_serializes_to_json"));
    }

    #[test]
    fn structured_test_log_failed_requires_repro_seed_or_fixture() {
        let mut env = BTreeMap::new();
        env.insert("os".to_owned(), "linux".to_owned());

        let log = StructuredTestLog {
            schema_version: "1.0.0".to_owned(),
            ts_unix_ms: 1,
            crate_name: "fnx-runtime".to_owned(),
            packet_id: "FNX-P2C-FOUNDATION".to_owned(),
            test_name: "failure_case".to_owned(),
            test_kind: TestKind::Property,
            mode: CompatibilityMode::Hardened,
            fixture_id: None,
            seed: None,
            environment: env,
            artifact_refs: vec!["artifacts/conformance/latest/smoke_report.json".to_owned()],
            hash_id: "sha256:def456".to_owned(),
            status: TestStatus::Failed,
            failure_repro: Some(FailureReproData {
                failure_message: "expected no mismatch".to_owned(),
                reproduction_command: "cargo test -p fnx-conformance -- --nocapture".to_owned(),
                expected_behavior: "zero drift".to_owned(),
                observed_behavior: "mismatch_count=1".to_owned(),
                seed: None,
                fixture_id: None,
                artifact_hash_id: Some("sha256:def456".to_owned()),
            }),
        };

        let err = log
            .validate()
            .expect_err("failed status without seed/fixture should reject");
        assert!(err.contains("seed or fixture_id"));
    }
}
