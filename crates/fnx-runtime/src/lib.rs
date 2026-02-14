#![forbid(unsafe_code)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

pub const STRUCTURED_TEST_LOG_SCHEMA_VERSION_V1: &str = "1.0.0";

#[must_use]
pub fn structured_test_log_schema_version() -> &'static str {
    STRUCTURED_TEST_LOG_SCHEMA_VERSION_V1
}

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
    Perf,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum TestStatus {
    Passed,
    Failed,
    Skipped,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum E2eStepStatus {
    Started,
    Passed,
    Failed,
    Skipped,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct E2eStepTrace {
    pub run_id: String,
    pub test_id: String,
    pub step_id: String,
    pub step_label: String,
    pub phase: String,
    pub status: E2eStepStatus,
    pub start_unix_ms: u128,
    pub end_unix_ms: u128,
    pub duration_ms: u128,
    pub replay_command: String,
    pub forensic_bundle_id: String,
    pub artifact_refs: Vec<String>,
    pub hash_id: String,
    pub reason_code: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ForensicsBundleIndex {
    pub bundle_id: String,
    pub run_id: String,
    pub test_id: String,
    pub bundle_hash_id: String,
    pub captured_unix_ms: u128,
    pub replay_ref: String,
    pub artifact_refs: Vec<String>,
    #[serde(default)]
    pub raptorq_sidecar_refs: Vec<String>,
    #[serde(default)]
    pub decode_proof_refs: Vec<String>,
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
    pub forensics_link: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct StructuredTestLog {
    pub schema_version: String,
    pub run_id: String,
    pub ts_unix_ms: u128,
    pub crate_name: String,
    pub suite_id: String,
    pub packet_id: String,
    pub test_name: String,
    pub test_id: String,
    pub test_kind: TestKind,
    pub mode: CompatibilityMode,
    pub fixture_id: Option<String>,
    pub seed: Option<u64>,
    pub environment: BTreeMap<String, String>,
    pub env_fingerprint: String,
    pub duration_ms: u128,
    pub replay_command: String,
    pub artifact_refs: Vec<String>,
    pub forensic_bundle_id: String,
    pub hash_id: String,
    pub status: TestStatus,
    pub reason_code: Option<String>,
    pub failure_repro: Option<FailureReproData>,
    #[serde(default)]
    pub e2e_step_traces: Vec<E2eStepTrace>,
    #[serde(default)]
    pub forensics_bundle_index: Option<ForensicsBundleIndex>,
}

impl StructuredTestLog {
    pub fn validate(&self) -> Result<(), String> {
        if self.schema_version.trim().is_empty() {
            return Err("schema_version must be non-empty".to_owned());
        }
        if self.schema_version != structured_test_log_schema_version() {
            return Err(format!(
                "unsupported schema_version `{}` (expected `{}`)",
                self.schema_version,
                structured_test_log_schema_version()
            ));
        }
        if self.run_id.trim().is_empty() {
            return Err("run_id must be non-empty".to_owned());
        }
        if self.crate_name.trim().is_empty() {
            return Err("crate_name must be non-empty".to_owned());
        }
        if self.suite_id.trim().is_empty() {
            return Err("suite_id must be non-empty".to_owned());
        }
        if self.packet_id.trim().is_empty() {
            return Err("packet_id must be non-empty".to_owned());
        }
        if self.test_name.trim().is_empty() {
            return Err("test_name must be non-empty".to_owned());
        }
        if self.test_id.trim().is_empty() {
            return Err("test_id must be non-empty".to_owned());
        }
        if self.env_fingerprint.trim().is_empty() {
            return Err("env_fingerprint must be non-empty".to_owned());
        }
        if self.replay_command.trim().is_empty() {
            return Err("replay_command must be non-empty".to_owned());
        }
        if self.forensic_bundle_id.trim().is_empty() {
            return Err("forensic_bundle_id must be non-empty".to_owned());
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
        if self
            .artifact_refs
            .iter()
            .any(|artifact_ref| artifact_ref.trim().is_empty())
        {
            return Err("artifact_refs must not contain empty entries".to_owned());
        }
        let Some(bundle_index) = &self.forensics_bundle_index else {
            return Err("forensics_bundle_index is required".to_owned());
        };
        if bundle_index.bundle_id.trim().is_empty() {
            return Err("forensics_bundle_index.bundle_id must be non-empty".to_owned());
        }
        if bundle_index.bundle_hash_id.trim().is_empty() {
            return Err("forensics_bundle_index.bundle_hash_id must be non-empty".to_owned());
        }
        if bundle_index.replay_ref.trim().is_empty() {
            return Err("forensics_bundle_index.replay_ref must be non-empty".to_owned());
        }
        if bundle_index.artifact_refs.is_empty() {
            return Err("forensics_bundle_index.artifact_refs must be non-empty".to_owned());
        }
        if bundle_index
            .artifact_refs
            .iter()
            .any(|artifact_ref| artifact_ref.trim().is_empty())
        {
            return Err(
                "forensics_bundle_index.artifact_refs must not contain empty entries".to_owned(),
            );
        }
        if bundle_index.bundle_id != self.forensic_bundle_id {
            return Err(
                "forensics_bundle_index.bundle_id must match forensic_bundle_id".to_owned(),
            );
        }
        if bundle_index.run_id != self.run_id {
            return Err("forensics_bundle_index.run_id must match run_id".to_owned());
        }
        if bundle_index.test_id != self.test_id {
            return Err("forensics_bundle_index.test_id must match test_id".to_owned());
        }
        if bundle_index.replay_ref != self.replay_command {
            return Err("forensics_bundle_index.replay_ref must match replay_command".to_owned());
        }

        match self.status {
            TestStatus::Failed => {
                let Some(failure) = &self.failure_repro else {
                    return Err("failure_repro is required when status=failed".to_owned());
                };
                let Some(reason_code) = &self.reason_code else {
                    return Err("reason_code is required when status=failed".to_owned());
                };
                if reason_code.trim().is_empty() {
                    return Err("reason_code must be non-empty when status=failed".to_owned());
                }
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
                let Some(artifact_hash_id) = &failure.artifact_hash_id else {
                    return Err("failed status requires artifact_hash_id".to_owned());
                };
                if artifact_hash_id.trim().is_empty() {
                    return Err("artifact_hash_id must be non-empty for failed status".to_owned());
                }
                if let Some(forensics_link) = &failure.forensics_link
                    && forensics_link.trim().is_empty()
                {
                    return Err("forensics_link must be non-empty when provided".to_owned());
                }
            }
            TestStatus::Skipped => {
                if self
                    .reason_code
                    .as_deref()
                    .is_none_or(|value| value.trim().is_empty())
                {
                    return Err("reason_code is required when status=skipped".to_owned());
                }
                if self.failure_repro.is_some() {
                    return Err("failure_repro must be omitted unless status=failed".to_owned());
                }
            }
            TestStatus::Passed => {
                if let Some(reason_code) = &self.reason_code
                    && reason_code.trim().is_empty()
                {
                    return Err("reason_code must be non-empty when provided".to_owned());
                }
                if self.failure_repro.is_some() {
                    return Err("failure_repro must be omitted unless status=failed".to_owned());
                }
            }
        }

        if self.test_kind == TestKind::E2e && self.e2e_step_traces.is_empty() {
            return Err("e2e_step_traces are required when test_kind=e2e".to_owned());
        }
        let mut seen_step_ids = std::collections::BTreeSet::new();
        for step in &self.e2e_step_traces {
            if step.run_id.trim().is_empty() {
                return Err("e2e_step_traces.run_id must be non-empty".to_owned());
            }
            if step.test_id.trim().is_empty() {
                return Err("e2e_step_traces.test_id must be non-empty".to_owned());
            }
            if step.step_id.trim().is_empty() {
                return Err("e2e_step_traces.step_id must be non-empty".to_owned());
            }
            if !seen_step_ids.insert(step.step_id.clone()) {
                return Err("e2e_step_traces.step_id values must be unique".to_owned());
            }
            if step.step_label.trim().is_empty() {
                return Err("e2e_step_traces.step_label must be non-empty".to_owned());
            }
            if step.phase.trim().is_empty() {
                return Err("e2e_step_traces.phase must be non-empty".to_owned());
            }
            if step.start_unix_ms > step.end_unix_ms {
                return Err("e2e_step_traces start_unix_ms must be <= end_unix_ms".to_owned());
            }
            let observed_duration = step.end_unix_ms.saturating_sub(step.start_unix_ms);
            if step.duration_ms != observed_duration {
                return Err(
                    "e2e_step_traces duration_ms must match end_unix_ms - start_unix_ms".to_owned(),
                );
            }
            if step.replay_command.trim().is_empty() {
                return Err("e2e_step_traces.replay_command must be non-empty".to_owned());
            }
            if step.hash_id.trim().is_empty() {
                return Err("e2e_step_traces.hash_id must be non-empty".to_owned());
            }
            if step.forensic_bundle_id.trim().is_empty() {
                return Err("e2e_step_traces.forensic_bundle_id must be non-empty".to_owned());
            }
            if step.artifact_refs.is_empty() {
                return Err("e2e_step_traces.artifact_refs must be non-empty".to_owned());
            }
            if step
                .artifact_refs
                .iter()
                .any(|artifact_ref| artifact_ref.trim().is_empty())
            {
                return Err(
                    "e2e_step_traces.artifact_refs must not contain empty entries".to_owned(),
                );
            }
            if step.run_id != self.run_id {
                return Err("e2e_step_traces.run_id must match run_id".to_owned());
            }
            if step.test_id != self.test_id {
                return Err("e2e_step_traces.test_id must match test_id".to_owned());
            }
            if step.forensic_bundle_id != self.forensic_bundle_id {
                return Err(
                    "e2e_step_traces.forensic_bundle_id must match forensic_bundle_id".to_owned(),
                );
            }
            if step.replay_command != self.replay_command {
                return Err("e2e_step_traces.replay_command must match replay_command".to_owned());
            }
            match step.status {
                E2eStepStatus::Failed | E2eStepStatus::Skipped => {
                    if step
                        .reason_code
                        .as_deref()
                        .is_none_or(|reason_code| reason_code.trim().is_empty())
                    {
                        return Err(
                            "e2e_step_traces.reason_code is required for failed/skipped step status"
                                .to_owned(),
                        );
                    }
                }
                E2eStepStatus::Started | E2eStepStatus::Passed => {
                    if let Some(reason_code) = &step.reason_code
                        && reason_code.trim().is_empty()
                    {
                        return Err(
                            "e2e_step_traces.reason_code must be non-empty when provided"
                                .to_owned(),
                        );
                    }
                }
            }
        }

        Ok(())
    }

    pub fn to_json_pretty(&self) -> Result<String, serde_json::Error> {
        serde_json::to_string_pretty(self)
    }
}

#[must_use]
pub fn canonical_environment_fingerprint(environment: &BTreeMap<String, String>) -> String {
    let canonical = environment
        .iter()
        .map(|(key, value)| format!("{key}={value}"))
        .collect::<Vec<String>>()
        .join("\n");
    stable_hash_hex(canonical.as_bytes())
}

fn stable_hash_hex(input: &[u8]) -> String {
    let mut hash = 0xcbf29ce484222325_u64;
    for byte in input {
        hash ^= u64::from(*byte);
        hash = hash.wrapping_mul(0x00000100000001B3_u64);
    }
    format!("{hash:016x}")
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
        CompatibilityMode, DecisionAction, E2eStepStatus, E2eStepTrace, EvidenceLedger,
        FailureReproData, ForensicsBundleIndex, StructuredTestLog, TestKind, TestStatus,
        canonical_environment_fingerprint, decision_theoretic_action,
        structured_test_log_schema_version,
    };
    use std::collections::BTreeMap;

    fn base_env() -> BTreeMap<String, String> {
        let mut env = BTreeMap::new();
        env.insert("arch".to_owned(), "x86_64".to_owned());
        env.insert("os".to_owned(), "linux".to_owned());
        env
    }

    fn base_forensics_bundle(
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
            bundle_hash_id: "bundle_hash_123".to_owned(),
            captured_unix_ms: 1,
            replay_ref: replay_ref.to_owned(),
            artifact_refs,
            raptorq_sidecar_refs: Vec::new(),
            decode_proof_refs: Vec::new(),
        }
    }

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
        let env = base_env();

        let log = StructuredTestLog {
            schema_version: structured_test_log_schema_version().to_owned(),
            run_id: "run-1".to_owned(),
            ts_unix_ms: 1,
            crate_name: "fnx-runtime".to_owned(),
            suite_id: "unit".to_owned(),
            packet_id: "FNX-P2C-FOUNDATION".to_owned(),
            test_name: "ledger_serializes_to_json".to_owned(),
            test_id: "tests::ledger_serializes_to_json".to_owned(),
            test_kind: TestKind::Unit,
            mode: CompatibilityMode::Strict,
            fixture_id: None,
            seed: Some(7),
            env_fingerprint: canonical_environment_fingerprint(&env),
            environment: env.clone(),
            duration_ms: 1,
            replay_command: "cargo test -p fnx-runtime ledger_serializes_to_json".to_owned(),
            artifact_refs: vec!["artifacts/conformance/latest/smoke_report.json".to_owned()],
            forensic_bundle_id: "forensics::unit::ledger".to_owned(),
            hash_id: "sha256:abc123".to_owned(),
            status: TestStatus::Passed,
            reason_code: None,
            failure_repro: None,
            e2e_step_traces: Vec::new(),
            forensics_bundle_index: Some(base_forensics_bundle(
                "run-1",
                "tests::ledger_serializes_to_json",
                "cargo test -p fnx-runtime ledger_serializes_to_json",
                "forensics::unit::ledger",
                vec!["artifacts/conformance/latest/smoke_report.json".to_owned()],
            )),
        };

        assert!(log.validate().is_ok());
        let json = log.to_json_pretty().expect("log should serialize");
        assert!(json.contains("ledger_serializes_to_json"));
    }

    #[test]
    fn structured_test_log_failed_requires_repro_seed_or_fixture() {
        let env = base_env();

        let log = StructuredTestLog {
            schema_version: structured_test_log_schema_version().to_owned(),
            run_id: "run-2".to_owned(),
            ts_unix_ms: 1,
            crate_name: "fnx-runtime".to_owned(),
            suite_id: "property".to_owned(),
            packet_id: "FNX-P2C-FOUNDATION".to_owned(),
            test_name: "failure_case".to_owned(),
            test_id: "tests::failure_case".to_owned(),
            test_kind: TestKind::Property,
            mode: CompatibilityMode::Hardened,
            fixture_id: None,
            seed: None,
            env_fingerprint: canonical_environment_fingerprint(&env),
            environment: env,
            duration_ms: 4,
            replay_command: "cargo test -p fnx-conformance -- --nocapture".to_owned(),
            artifact_refs: vec!["artifacts/conformance/latest/smoke_report.json".to_owned()],
            forensic_bundle_id: "forensics::prop::failure_case".to_owned(),
            hash_id: "sha256:def456".to_owned(),
            status: TestStatus::Failed,
            reason_code: Some("mismatch".to_owned()),
            failure_repro: Some(FailureReproData {
                failure_message: "expected no mismatch".to_owned(),
                reproduction_command: "cargo test -p fnx-conformance -- --nocapture".to_owned(),
                expected_behavior: "zero drift".to_owned(),
                observed_behavior: "mismatch_count=1".to_owned(),
                seed: None,
                fixture_id: None,
                artifact_hash_id: Some("sha256:def456".to_owned()),
                forensics_link: Some(
                    "artifacts/conformance/latest/failure_case.report.json".to_owned(),
                ),
            }),
            e2e_step_traces: Vec::new(),
            forensics_bundle_index: Some(base_forensics_bundle(
                "run-2",
                "tests::failure_case",
                "cargo test -p fnx-conformance -- --nocapture",
                "forensics::prop::failure_case",
                vec!["artifacts/conformance/latest/smoke_report.json".to_owned()],
            )),
        };

        let err = log
            .validate()
            .expect_err("failed status without seed/fixture should reject");
        assert!(err.contains("seed or fixture_id"));
    }

    #[test]
    fn structured_test_log_skipped_requires_reason_code() {
        let env = base_env();
        let log = StructuredTestLog {
            schema_version: structured_test_log_schema_version().to_owned(),
            run_id: "run-3".to_owned(),
            ts_unix_ms: 1,
            crate_name: "fnx-runtime".to_owned(),
            suite_id: "integration".to_owned(),
            packet_id: "FNX-P2C-FOUNDATION".to_owned(),
            test_name: "skip_case".to_owned(),
            test_id: "tests::skip_case".to_owned(),
            test_kind: TestKind::Unit,
            mode: CompatibilityMode::Strict,
            fixture_id: None,
            seed: Some(1),
            env_fingerprint: canonical_environment_fingerprint(&env),
            environment: env,
            duration_ms: 0,
            replay_command: "cargo test -p fnx-conformance skip_case -- --nocapture".to_owned(),
            artifact_refs: vec!["artifacts/conformance/latest/skip_case.report.json".to_owned()],
            forensic_bundle_id: "forensics::integration::skip_case".to_owned(),
            hash_id: "sha256:skip".to_owned(),
            status: TestStatus::Skipped,
            reason_code: None,
            failure_repro: None,
            e2e_step_traces: Vec::new(),
            forensics_bundle_index: Some(base_forensics_bundle(
                "run-3",
                "tests::skip_case",
                "cargo test -p fnx-conformance skip_case -- --nocapture",
                "forensics::integration::skip_case",
                vec!["artifacts/conformance/latest/skip_case.report.json".to_owned()],
            )),
        };

        let err = log
            .validate()
            .expect_err("skipped status without reason code should reject");
        assert!(err.contains("reason_code is required"));
    }

    #[test]
    fn structured_test_log_e2e_requires_step_traces() {
        let env = base_env();
        let log = StructuredTestLog {
            schema_version: structured_test_log_schema_version().to_owned(),
            run_id: "run-3b".to_owned(),
            ts_unix_ms: 10,
            crate_name: "fnx-runtime".to_owned(),
            suite_id: "integration".to_owned(),
            packet_id: "FNX-P2C-FOUNDATION".to_owned(),
            test_name: "e2e_no_steps".to_owned(),
            test_id: "tests::e2e_no_steps".to_owned(),
            test_kind: TestKind::E2e,
            mode: CompatibilityMode::Strict,
            fixture_id: None,
            seed: Some(1),
            env_fingerprint: canonical_environment_fingerprint(&env),
            environment: env,
            duration_ms: 5,
            replay_command: "cargo test -p fnx-conformance e2e_no_steps -- --nocapture".to_owned(),
            artifact_refs: vec!["artifacts/conformance/latest/e2e_no_steps.report.json".to_owned()],
            forensic_bundle_id: "forensics::integration::e2e_no_steps".to_owned(),
            hash_id: "sha256:e2e-no-steps".to_owned(),
            status: TestStatus::Passed,
            reason_code: None,
            failure_repro: None,
            e2e_step_traces: Vec::new(),
            forensics_bundle_index: Some(base_forensics_bundle(
                "run-3b",
                "tests::e2e_no_steps",
                "cargo test -p fnx-conformance e2e_no_steps -- --nocapture",
                "forensics::integration::e2e_no_steps",
                vec!["artifacts/conformance/latest/e2e_no_steps.report.json".to_owned()],
            )),
        };

        let err = log
            .validate()
            .expect_err("e2e logs without steps should reject");
        assert!(err.contains("e2e_step_traces are required"));
    }

    #[test]
    fn structured_test_log_rejects_step_trace_bundle_mismatch() {
        let env = base_env();
        let replay = "cargo test -p fnx-conformance e2e_bundle_mismatch -- --nocapture";
        let log = StructuredTestLog {
            schema_version: structured_test_log_schema_version().to_owned(),
            run_id: "run-3c".to_owned(),
            ts_unix_ms: 100,
            crate_name: "fnx-runtime".to_owned(),
            suite_id: "integration".to_owned(),
            packet_id: "FNX-P2C-FOUNDATION".to_owned(),
            test_name: "e2e_bundle_mismatch".to_owned(),
            test_id: "tests::e2e_bundle_mismatch".to_owned(),
            test_kind: TestKind::E2e,
            mode: CompatibilityMode::Strict,
            fixture_id: None,
            seed: Some(1),
            env_fingerprint: canonical_environment_fingerprint(&env),
            environment: env,
            duration_ms: 3,
            replay_command: replay.to_owned(),
            artifact_refs: vec![
                "artifacts/conformance/latest/e2e_bundle_mismatch.report.json".to_owned(),
            ],
            forensic_bundle_id: "forensics::integration::bundle_a".to_owned(),
            hash_id: "sha256:e2e-bundle-mismatch".to_owned(),
            status: TestStatus::Passed,
            reason_code: None,
            failure_repro: None,
            e2e_step_traces: vec![E2eStepTrace {
                run_id: "run-3c".to_owned(),
                test_id: "tests::e2e_bundle_mismatch".to_owned(),
                step_id: "step-1".to_owned(),
                step_label: "setup".to_owned(),
                phase: "arrange".to_owned(),
                status: E2eStepStatus::Passed,
                start_unix_ms: 100,
                end_unix_ms: 101,
                duration_ms: 1,
                replay_command: replay.to_owned(),
                forensic_bundle_id: "forensics::integration::bundle_b".to_owned(),
                artifact_refs: vec![
                    "artifacts/conformance/latest/e2e_bundle_mismatch.report.json".to_owned(),
                ],
                hash_id: "step-hash-1".to_owned(),
                reason_code: None,
            }],
            forensics_bundle_index: Some(base_forensics_bundle(
                "run-3c",
                "tests::e2e_bundle_mismatch",
                replay,
                "forensics::integration::bundle_a",
                vec!["artifacts/conformance/latest/e2e_bundle_mismatch.report.json".to_owned()],
            )),
        };

        let err = log
            .validate()
            .expect_err("step trace bundle id mismatch should reject");
        assert!(err.contains("e2e_step_traces.forensic_bundle_id must match"));
    }

    #[test]
    fn structured_test_log_rejects_unknown_schema_version() {
        let env = base_env();
        let log = StructuredTestLog {
            schema_version: "9.9.9".to_owned(),
            run_id: "run-4".to_owned(),
            ts_unix_ms: 1,
            crate_name: "fnx-runtime".to_owned(),
            suite_id: "integration".to_owned(),
            packet_id: "FNX-P2C-FOUNDATION".to_owned(),
            test_name: "schema_gate".to_owned(),
            test_id: "tests::schema_gate".to_owned(),
            test_kind: TestKind::Unit,
            mode: CompatibilityMode::Strict,
            fixture_id: None,
            seed: Some(1),
            env_fingerprint: canonical_environment_fingerprint(&env),
            environment: env,
            duration_ms: 0,
            replay_command: "cargo test -p fnx-runtime schema_gate".to_owned(),
            artifact_refs: vec!["artifacts/conformance/latest/schema_gate.report.json".to_owned()],
            forensic_bundle_id: "forensics::schema_gate".to_owned(),
            hash_id: "sha256:schema-gate".to_owned(),
            status: TestStatus::Passed,
            reason_code: None,
            failure_repro: None,
            e2e_step_traces: Vec::new(),
            forensics_bundle_index: Some(base_forensics_bundle(
                "run-4",
                "tests::schema_gate",
                "cargo test -p fnx-runtime schema_gate",
                "forensics::schema_gate",
                vec!["artifacts/conformance/latest/schema_gate.report.json".to_owned()],
            )),
        };

        let err = log
            .validate()
            .expect_err("unsupported schema version should fail closed");
        assert!(err.contains("unsupported schema_version"));
    }
}
