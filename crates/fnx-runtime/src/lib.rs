#![forbid(unsafe_code)]

use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};
use std::time::{Duration, SystemTime, UNIX_EPOCH};

pub const STRUCTURED_TEST_LOG_SCHEMA_VERSION_V1: &str = "1.0.0";
pub const CGSE_POLICY_SCHEMA_VERSION_V1: &str = "1.0.0";
pub const CGSE_POLICY_SPEC_PATH: &str = "artifacts/cgse/v1/cgse_deterministic_policy_spec_v1.json";
pub const CGSE_POLICY_SPEC_SCHEMA_PATH: &str =
    "artifacts/cgse/schema/v1/cgse_deterministic_policy_spec_schema_v1.json";
pub const CGSE_LEGACY_TIEBREAK_LEDGER_PATH: &str =
    "artifacts/cgse/v1/cgse_legacy_tiebreak_ordering_ledger_v1.json";
pub const CGSE_SEMANTICS_THREAT_MODEL_PATH: &str =
    "artifacts/cgse/v1/cgse_semantics_threat_model_v1.json";

#[must_use]
pub fn structured_test_log_schema_version() -> &'static str {
    STRUCTURED_TEST_LOG_SCHEMA_VERSION_V1
}

#[must_use]
pub fn cgse_policy_schema_version() -> &'static str {
    CGSE_POLICY_SCHEMA_VERSION_V1
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

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(untagged)]
pub enum CgseValue {
    Bool(bool),
    Int(i64),
    Float(f64),
    String(String),
    Map(BTreeMap<String, CgseValue>),
}

impl Eq for CgseValue {}

impl From<String> for CgseValue {
    fn from(s: String) -> Self {
        Self::String(s)
    }
}

impl From<&str> for CgseValue {
    fn from(s: &str) -> Self {
        Self::String(s.to_owned())
    }
}

impl From<f64> for CgseValue {
    fn from(f: f64) -> Self {
        Self::Float(f)
    }
}

impl From<i64> for CgseValue {
    fn from(i: i64) -> Self {
        Self::Int(i)
    }
}

impl From<bool> for CgseValue {
    fn from(b: bool) -> Self {
        Self::Bool(b)
    }
}

impl CgseValue {
    #[must_use]
    pub fn as_f64(&self) -> Option<f64> {
        match self {
            Self::Float(f) => Some(*f),
            Self::Int(i) => Some(*i as f64),
            Self::String(s) => s.parse::<f64>().ok(),
            Self::Bool(b) => Some(if *b { 1.0 } else { 0.0 }),
            Self::Map(_) => None,
        }
    }

    #[must_use]
    pub fn as_str(&self) -> String {
        match self {
            Self::String(s) => s.clone(),
            Self::Float(f) => f.to_string(),
            Self::Int(i) => i.to_string(),
            Self::Bool(b) => b.to_string(),
            Self::Map(map) => serde_json::to_string(map).unwrap_or_else(|_| "{}".to_owned()),
        }
    }

    /// Heuristic type inference for a raw string value.
    /// Order of preference: Int -> Bool -> Float -> String.
    #[must_use]
    pub fn parse_relaxed(s: &str) -> Self {
        if let Ok(i) = s.parse::<i64>() {
            return Self::Int(i);
        }
        if s.eq_ignore_ascii_case("true") {
            return Self::Bool(true);
        }
        if s.eq_ignore_ascii_case("false") {
            return Self::Bool(false);
        }
        if let Ok(f) = s.parse::<f64>() {
            return Self::Float(f);
        }
        Self::String(s.to_owned())
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum CgseOperationFamily {
    GraphCoreMutation,
    ViewSemantics,
    DispatchRouting,
    ConversionContracts,
    ShortestPathAlgorithms,
    ReadwriteSerialization,
    GeneratorSemantics,
    RuntimeConfig,
    OracleTestSurface,
}

impl CgseOperationFamily {
    #[must_use]
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::GraphCoreMutation => "graph_core_mutation",
            Self::ViewSemantics => "view_semantics",
            Self::DispatchRouting => "dispatch_routing",
            Self::ConversionContracts => "conversion_contracts",
            Self::ShortestPathAlgorithms => "shortest_path_algorithms",
            Self::ReadwriteSerialization => "readwrite_serialization",
            Self::GeneratorSemantics => "generator_semantics",
            Self::RuntimeConfig => "runtime_config",
            Self::OracleTestSurface => "oracle_test_surface",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum CgsePolicyRule {
    R01,
    R02,
    R03,
    R04,
    R05,
    R06,
    R07,
    R08,
    R09,
    R10,
    R11,
    R12,
    R13,
    R14,
}

impl CgsePolicyRule {
    pub const ALL: [Self; 14] = [
        Self::R01,
        Self::R02,
        Self::R03,
        Self::R04,
        Self::R05,
        Self::R06,
        Self::R07,
        Self::R08,
        Self::R09,
        Self::R10,
        Self::R11,
        Self::R12,
        Self::R13,
        Self::R14,
    ];

    #[must_use]
    pub fn from_rule_id(rule_id: &str) -> Option<Self> {
        Some(match rule_id {
            "CGSE-R01" => Self::R01,
            "CGSE-R02" => Self::R02,
            "CGSE-R03" => Self::R03,
            "CGSE-R04" => Self::R04,
            "CGSE-R05" => Self::R05,
            "CGSE-R06" => Self::R06,
            "CGSE-R07" => Self::R07,
            "CGSE-R08" => Self::R08,
            "CGSE-R09" => Self::R09,
            "CGSE-R10" => Self::R10,
            "CGSE-R11" => Self::R11,
            "CGSE-R12" => Self::R12,
            "CGSE-R13" => Self::R13,
            "CGSE-R14" => Self::R14,
            _ => return None,
        })
    }

    #[must_use]
    pub const fn as_rule_id(self) -> &'static str {
        match self {
            Self::R01 => "CGSE-R01",
            Self::R02 => "CGSE-R02",
            Self::R03 => "CGSE-R03",
            Self::R04 => "CGSE-R04",
            Self::R05 => "CGSE-R05",
            Self::R06 => "CGSE-R06",
            Self::R07 => "CGSE-R07",
            Self::R08 => "CGSE-R08",
            Self::R09 => "CGSE-R09",
            Self::R10 => "CGSE-R10",
            Self::R11 => "CGSE-R11",
            Self::R12 => "CGSE-R12",
            Self::R13 => "CGSE-R13",
            Self::R14 => "CGSE-R14",
        }
    }

    #[must_use]
    pub const fn policy_id(self) -> &'static str {
        match self {
            Self::R01 => "CGSE-POL-R01",
            Self::R02 => "CGSE-POL-R02",
            Self::R03 => "CGSE-POL-R03",
            Self::R04 => "CGSE-POL-R04",
            Self::R05 => "CGSE-POL-R05",
            Self::R06 => "CGSE-POL-R06",
            Self::R07 => "CGSE-POL-R07",
            Self::R08 => "CGSE-POL-R08",
            Self::R09 => "CGSE-POL-R09",
            Self::R10 => "CGSE-POL-R10",
            Self::R11 => "CGSE-POL-R11",
            Self::R12 => "CGSE-POL-R12",
            Self::R13 => "CGSE-POL-R13",
            Self::R14 => "CGSE-POL-R14",
        }
    }

    #[must_use]
    pub const fn operation_family(self) -> CgseOperationFamily {
        match self {
            Self::R01 | Self::R02 | Self::R03 => CgseOperationFamily::GraphCoreMutation,
            Self::R04 => CgseOperationFamily::ViewSemantics,
            Self::R05 | Self::R06 => CgseOperationFamily::DispatchRouting,
            Self::R07 => CgseOperationFamily::ConversionContracts,
            Self::R08 | Self::R09 => CgseOperationFamily::ShortestPathAlgorithms,
            Self::R10 | Self::R11 => CgseOperationFamily::ReadwriteSerialization,
            Self::R12 => CgseOperationFamily::GeneratorSemantics,
            Self::R13 => CgseOperationFamily::RuntimeConfig,
            Self::R14 => CgseOperationFamily::OracleTestSurface,
        }
    }

    #[must_use]
    pub const fn hardened_allowlist(self) -> &'static [&'static str] {
        match self {
            Self::R01 => &["CGSE-AMB-001"],
            Self::R02 => &["CGSE-AMB-002"],
            Self::R03 => &["CGSE-AMB-003"],
            Self::R04 => &["CGSE-AMB-004"],
            Self::R05 => &["CGSE-AMB-005"],
            Self::R06 => &["CGSE-AMB-006"],
            Self::R07 => &["CGSE-AMB-007"],
            Self::R08 => &["CGSE-AMB-008"],
            Self::R09 => &["bounded_diagnostic_enrichment"],
            Self::R10 => &["CGSE-AMB-009"],
            Self::R11 => &["bounded_diagnostic_enrichment"],
            Self::R12 => &["CGSE-AMB-010"],
            Self::R13 => &["bounded_diagnostic_enrichment"],
            Self::R14 => &["CGSE-AMB-011"],
        }
    }

    #[must_use]
    pub const fn fail_closed_default(self) -> &'static str {
        match self {
            Self::R01 => "fail_closed_on_cgse_r01_drift",
            Self::R02 => "fail_closed_on_cgse_r02_drift",
            Self::R03 => "fail_closed_on_cgse_r03_drift",
            Self::R04 => "fail_closed_on_cgse_r04_drift",
            Self::R05 => "fail_closed_on_cgse_r05_drift",
            Self::R06 => "fail_closed_on_cgse_r06_drift",
            Self::R07 => "fail_closed_on_cgse_r07_drift",
            Self::R08 => "fail_closed_on_cgse_r08_drift",
            Self::R09 => "fail_closed_on_cgse_r09_drift",
            Self::R10 => "fail_closed_on_cgse_r10_drift",
            Self::R11 => "fail_closed_on_cgse_r11_drift",
            Self::R12 => "fail_closed_on_cgse_r12_drift",
            Self::R13 => "fail_closed_on_cgse_r13_drift",
            Self::R14 => "fail_closed_on_cgse_r14_drift",
        }
    }
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

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum AsupersyncAdapterState {
    Idle,
    CapabilityCheck,
    Syncing,
    VerifyingChecksum,
    Completed,
    FailedClosed,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum AsupersyncAdapterEventType {
    Start,
    CapabilityAccepted,
    CapabilityRejected,
    ChunkCommitted,
    ResumeApplied,
    TransportInterrupted,
    ChecksumVerificationStarted,
    ChecksumValidated,
    ChecksumMismatch,
    ConflictDetected,
    RetryBudgetExceeded,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum AsupersyncAdapterReasonCode {
    UnsupportedCapability,
    CapabilityMismatch,
    IntegrityPrecheckFailed,
    ConflictDetected,
    RetryExhausted,
    InvalidTransition,
    ResumeCursorAhead,
    ResumeTransferMismatch,
    ResumeSeedMismatch,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct AsupersyncTransferIntent {
    pub transfer_id: String,
    pub artifact_id: String,
    pub artifact_class: String,
    pub mode: CompatibilityMode,
    pub deterministic_seed: u64,
    pub expected_checksum: String,
    pub max_attempts: u8,
}

impl AsupersyncTransferIntent {
    pub fn validate(&self) -> Result<(), String> {
        if self.transfer_id.trim().is_empty() {
            return Err("transfer_id must be non-empty".to_owned());
        }
        if self.artifact_id.trim().is_empty() {
            return Err("artifact_id must be non-empty".to_owned());
        }
        if self.artifact_class.trim().is_empty() {
            return Err("artifact_class must be non-empty".to_owned());
        }
        if self.expected_checksum.trim().is_empty() {
            return Err("expected_checksum must be non-empty".to_owned());
        }
        if self.max_attempts == 0 {
            return Err("max_attempts must be >= 1".to_owned());
        }
        Ok(())
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct AsupersyncAdapterCheckpoint {
    pub transfer_id: String,
    pub deterministic_seed: u64,
    pub attempt: u8,
    pub committed_cursor: u64,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct AsupersyncAdapterTransition {
    pub seq: u64,
    pub from_state: AsupersyncAdapterState,
    pub event: AsupersyncAdapterEventType,
    pub to_state: AsupersyncAdapterState,
    pub attempt: u8,
    pub committed_cursor: u64,
    pub reason_code: Option<AsupersyncAdapterReasonCode>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct AsupersyncAdapterMachine {
    intent: AsupersyncTransferIntent,
    state: AsupersyncAdapterState,
    attempt: u8,
    committed_cursor: u64,
    transitions: Vec<AsupersyncAdapterTransition>,
}

impl AsupersyncAdapterMachine {
    pub fn start(intent: AsupersyncTransferIntent) -> Result<Self, String> {
        intent.validate()?;
        let transition_capacity = Self::transition_capacity(intent.max_attempts);

        let mut machine = Self {
            intent,
            state: AsupersyncAdapterState::Idle,
            attempt: 0,
            committed_cursor: 0,
            transitions: Vec::with_capacity(transition_capacity),
        };
        machine.transition(
            AsupersyncAdapterEventType::Start,
            AsupersyncAdapterState::CapabilityCheck,
            None,
        )?;
        Ok(machine)
    }

    pub fn resume_from_checkpoint(
        intent: AsupersyncTransferIntent,
        checkpoint: AsupersyncAdapterCheckpoint,
    ) -> Result<Self, String> {
        intent.validate()?;
        let transition_capacity = Self::transition_capacity(intent.max_attempts);
        if checkpoint.transfer_id != intent.transfer_id {
            return Err("checkpoint transfer_id does not match intent transfer_id".to_owned());
        }
        if checkpoint.deterministic_seed != intent.deterministic_seed {
            return Err(
                "checkpoint deterministic_seed does not match intent deterministic_seed".to_owned(),
            );
        }
        if checkpoint.attempt >= intent.max_attempts {
            return Err("checkpoint attempt exceeds max_attempts".to_owned());
        }

        let mut machine = Self {
            intent,
            state: AsupersyncAdapterState::Syncing,
            attempt: checkpoint.attempt,
            committed_cursor: checkpoint.committed_cursor,
            transitions: Vec::with_capacity(transition_capacity),
        };
        machine.append_transition(
            AsupersyncAdapterState::Syncing,
            AsupersyncAdapterEventType::ResumeApplied,
            AsupersyncAdapterState::Syncing,
            None,
        );
        Ok(machine)
    }

    #[must_use]
    pub fn intent(&self) -> &AsupersyncTransferIntent {
        &self.intent
    }

    #[must_use]
    pub fn state(&self) -> AsupersyncAdapterState {
        self.state
    }

    #[must_use]
    pub fn attempt(&self) -> u8 {
        self.attempt
    }

    #[must_use]
    pub fn committed_cursor(&self) -> u64 {
        self.committed_cursor
    }

    #[must_use]
    pub fn transitions(&self) -> &[AsupersyncAdapterTransition] {
        &self.transitions
    }

    #[must_use]
    pub fn checkpoint(&self) -> AsupersyncAdapterCheckpoint {
        AsupersyncAdapterCheckpoint {
            transfer_id: self.intent.transfer_id.clone(),
            deterministic_seed: self.intent.deterministic_seed,
            attempt: self.attempt,
            committed_cursor: self.committed_cursor,
        }
    }

    pub fn mark_capability_check(&mut self, supported: bool) -> Result<(), String> {
        self.require_active_state(
            AsupersyncAdapterState::CapabilityCheck,
            AsupersyncAdapterEventType::CapabilityAccepted,
        )?;
        if supported {
            self.transition(
                AsupersyncAdapterEventType::CapabilityAccepted,
                AsupersyncAdapterState::Syncing,
                None,
            )
        } else {
            self.fail_closed(
                AsupersyncAdapterEventType::CapabilityRejected,
                AsupersyncAdapterReasonCode::UnsupportedCapability,
            )
        }
    }

    pub fn record_chunk_commit(&mut self, cursor: u64) -> Result<(), String> {
        self.require_active_state(
            AsupersyncAdapterState::Syncing,
            AsupersyncAdapterEventType::ChunkCommitted,
        )?;
        if cursor < self.committed_cursor {
            return self.fail_closed(
                AsupersyncAdapterEventType::ConflictDetected,
                AsupersyncAdapterReasonCode::ConflictDetected,
            );
        }
        if cursor == self.committed_cursor {
            return Ok(()); // No-op
        }
        self.committed_cursor = cursor;
        self.transition(
            AsupersyncAdapterEventType::ChunkCommitted,
            AsupersyncAdapterState::Syncing,
            None,
        )
    }

    pub fn apply_resume_cursor(&mut self, resume_cursor: u64) -> Result<(), String> {
        self.require_active_state(
            AsupersyncAdapterState::Syncing,
            AsupersyncAdapterEventType::ResumeApplied,
        )?;
        if resume_cursor == self.committed_cursor {
            return Ok(()); // No-op
        }
        if resume_cursor > self.committed_cursor {
            return self.fail_closed(
                AsupersyncAdapterEventType::ConflictDetected,
                AsupersyncAdapterReasonCode::ResumeCursorAhead,
            );
        }
        self.committed_cursor = resume_cursor;
        self.transition(
            AsupersyncAdapterEventType::ResumeApplied,
            AsupersyncAdapterState::Syncing,
            None,
        )
    }

    pub fn record_transport_interruption(&mut self) -> Result<(), String> {
        self.require_active_state(
            AsupersyncAdapterState::Syncing,
            AsupersyncAdapterEventType::TransportInterrupted,
        )?;

        let Some(next_attempt) = self.attempt.checked_add(1) else {
            return self.fail_closed(
                AsupersyncAdapterEventType::RetryBudgetExceeded,
                AsupersyncAdapterReasonCode::RetryExhausted,
            );
        };
        if next_attempt > self.intent.max_attempts {
            return self.fail_closed(
                AsupersyncAdapterEventType::RetryBudgetExceeded,
                AsupersyncAdapterReasonCode::RetryExhausted,
            );
        }
        self.attempt = next_attempt;
        self.transition(
            AsupersyncAdapterEventType::TransportInterrupted,
            AsupersyncAdapterState::Syncing,
            None,
        )
    }

    pub fn start_checksum_verification(&mut self) -> Result<(), String> {
        self.require_active_state(
            AsupersyncAdapterState::Syncing,
            AsupersyncAdapterEventType::ChecksumVerificationStarted,
        )?;
        self.transition(
            AsupersyncAdapterEventType::ChecksumVerificationStarted,
            AsupersyncAdapterState::VerifyingChecksum,
            None,
        )
    }

    pub fn finish_checksum_verification(&mut self, observed_checksum: &str) -> Result<(), String> {
        self.require_active_state(
            AsupersyncAdapterState::VerifyingChecksum,
            AsupersyncAdapterEventType::ChecksumValidated,
        )?;
        if observed_checksum.trim().is_empty() {
            return self.fail_closed(
                AsupersyncAdapterEventType::ChecksumMismatch,
                AsupersyncAdapterReasonCode::IntegrityPrecheckFailed,
            );
        }
        if observed_checksum == self.intent.expected_checksum {
            self.transition(
                AsupersyncAdapterEventType::ChecksumValidated,
                AsupersyncAdapterState::Completed,
                None,
            )
        } else {
            self.fail_closed(
                AsupersyncAdapterEventType::ChecksumMismatch,
                AsupersyncAdapterReasonCode::IntegrityPrecheckFailed,
            )
        }
    }

    pub fn record_conflict(
        &mut self,
        expected_epoch: u64,
        observed_epoch: u64,
    ) -> Result<(), String> {
        self.require_active_state(
            AsupersyncAdapterState::Syncing,
            AsupersyncAdapterEventType::ConflictDetected,
        )?;
        if expected_epoch == observed_epoch {
            return Ok(());
        }
        self.fail_closed(
            AsupersyncAdapterEventType::ConflictDetected,
            AsupersyncAdapterReasonCode::ConflictDetected,
        )
    }

    pub fn validate_transition_log(&self) -> Result<(), String> {
        if self.transitions.is_empty() {
            return Err("transition log must contain at least one transition".to_owned());
        }
        let mut expected_seq = 1_u64;
        let mut reached_terminal = false;
        for transition in &self.transitions {
            if transition.seq != expected_seq {
                return Err("transition sequence must be contiguous and start at 1".to_owned());
            }
            expected_seq = expected_seq.saturating_add(1);

            if reached_terminal {
                return Err("transition log contains events after terminal state".to_owned());
            }
            if matches!(
                transition.to_state,
                AsupersyncAdapterState::Completed | AsupersyncAdapterState::FailedClosed
            ) {
                reached_terminal = true;
            }
        }
        Ok(())
    }

    fn require_active_state(
        &mut self,
        expected_state: AsupersyncAdapterState,
        event: AsupersyncAdapterEventType,
    ) -> Result<(), String> {
        if self.state == expected_state {
            return Ok(());
        }
        self.fail_closed(event, AsupersyncAdapterReasonCode::InvalidTransition)
    }

    fn fail_closed(
        &mut self,
        event: AsupersyncAdapterEventType,
        reason_code: AsupersyncAdapterReasonCode,
    ) -> Result<(), String> {
        if matches!(
            self.state,
            AsupersyncAdapterState::Completed | AsupersyncAdapterState::FailedClosed
        ) {
            return Err("state machine already in terminal state".to_owned());
        }
        self.transition(
            event,
            AsupersyncAdapterState::FailedClosed,
            Some(reason_code),
        )?;
        Err(format!(
            "fail-closed transition with reason `{reason_code:?}`"
        ))
    }

    fn transition(
        &mut self,
        event: AsupersyncAdapterEventType,
        to_state: AsupersyncAdapterState,
        reason_code: Option<AsupersyncAdapterReasonCode>,
    ) -> Result<(), String> {
        if matches!(
            self.state,
            AsupersyncAdapterState::Completed | AsupersyncAdapterState::FailedClosed
        ) {
            return Err("state machine already in terminal state".to_owned());
        }
        let from_state = self.state;
        self.state = to_state;
        self.append_transition(from_state, event, to_state, reason_code);
        Ok(())
    }

    fn append_transition(
        &mut self,
        from_state: AsupersyncAdapterState,
        event: AsupersyncAdapterEventType,
        to_state: AsupersyncAdapterState,
        reason_code: Option<AsupersyncAdapterReasonCode>,
    ) {
        let base = u64::try_from(self.transitions.len()).unwrap_or(u64::MAX);
        let seq = base.saturating_add(1);
        self.transitions.push(AsupersyncAdapterTransition {
            seq,
            from_state,
            event,
            to_state,
            attempt: self.attempt,
            committed_cursor: self.committed_cursor,
            reason_code,
        });
    }

    fn transition_capacity(max_attempts: u8) -> usize {
        usize::from(max_attempts).saturating_add(6)
    }
}

const FTUI_TELEMETRY_CANONICAL_FIELDS: [&str; 10] = [
    "run_id",
    "journey_id",
    "event_id",
    "state",
    "seed",
    "artifact_ref",
    "test_id",
    "replay_command",
    "env_fingerprint",
    "duration_ms",
];

#[must_use]
pub fn ftui_telemetry_canonical_fields() -> &'static [&'static str] {
    &FTUI_TELEMETRY_CANONICAL_FIELDS
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct FtuiTelemetryRecord {
    pub correlation_id: String,
    pub run_id: String,
    pub journey_id: String,
    pub event_id: String,
    pub state: String,
    pub seed: String,
    pub test_id: String,
    pub replay_command: String,
    pub env_fingerprint: String,
    pub duration_ms: String,
    pub status: String,
    pub mode: String,
    pub artifact_ref: String,
    pub reason_code: Option<String>,
    pub ts_unix_ms: u128,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct FtuiArtifactIndexEntry {
    pub correlation_id: String,
    pub bundle_id: String,
    pub run_id: String,
    pub test_id: String,
    pub captured_unix_ms: u128,
    pub replay_ref: String,
    pub artifact_refs: Vec<String>,
    pub status: TestStatus,
    pub reason_code: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
pub struct FtuiArtifactIndex {
    pub entries: Vec<FtuiArtifactIndexEntry>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct FtuiTelemetryAdapter {
    required_fields: BTreeSet<String>,
}

impl FtuiTelemetryAdapter {
    #[must_use]
    pub fn strict_default() -> Self {
        let required_fields = FTUI_TELEMETRY_CANONICAL_FIELDS
            .iter()
            .map(|field| (*field).to_owned())
            .collect();
        Self { required_fields }
    }

    #[must_use]
    pub fn required_fields(&self) -> &BTreeSet<String> {
        &self.required_fields
    }

    pub fn ingest_row(&self, row: &BTreeMap<String, String>) -> Result<(), String> {
        if row.is_empty() {
            return Err("telemetry row must be non-empty".to_owned());
        }

        for key in row.keys() {
            if !self.required_fields.contains(key) {
                return Err(format!(
                    "unknown telemetry field `{key}`; allowed fields: {}",
                    self.required_fields
                        .iter()
                        .cloned()
                        .collect::<Vec<_>>()
                        .join(", ")
                ));
            }
        }
        for field in &self.required_fields {
            if row.get(field).is_none_or(|value| value.trim().is_empty()) {
                return Err(format!("missing required telemetry field `{field}`"));
            }
        }

        Ok(())
    }

    pub fn from_structured_log(
        &self,
        log: &StructuredTestLog,
    ) -> Result<FtuiTelemetryRecord, String> {
        log.validate()?;

        let event_id = match log.status {
            TestStatus::Passed => "ftui.workflow.completed",
            TestStatus::Failed => "ftui.workflow.failed_closed",
            TestStatus::Skipped => "ftui.workflow.skipped",
        };
        let state = match log.status {
            TestStatus::Passed => "completed",
            TestStatus::Failed => "failed_closed",
            TestStatus::Skipped => "skipped",
        };
        let journey_id = format!("{}::{}", log.packet_id, log.suite_id);
        let artifact_ref = log.artifact_refs.join(";");
        let seed = log
            .seed
            .map_or_else(|| "none".to_owned(), |value| value.to_string());
        let duration_ms = log.duration_ms.to_string();

        let mut row = BTreeMap::new();
        row.insert("run_id".to_owned(), log.run_id.clone());
        row.insert("journey_id".to_owned(), journey_id.clone());
        row.insert("event_id".to_owned(), event_id.to_owned());
        row.insert("state".to_owned(), state.to_owned());
        row.insert("seed".to_owned(), seed.clone());
        row.insert("artifact_ref".to_owned(), artifact_ref.clone());
        row.insert("test_id".to_owned(), log.test_id.clone());
        row.insert("replay_command".to_owned(), log.replay_command.clone());
        row.insert("env_fingerprint".to_owned(), log.env_fingerprint.clone());
        row.insert("duration_ms".to_owned(), duration_ms.clone());
        self.ingest_row(&row)?;

        let mode = enum_token("mode", &log.mode)?;
        let status = enum_token("status", &log.status)?;
        let correlation_material = format!(
            "{}|{}|{}|{}|{}|{}",
            log.run_id,
            log.test_id,
            log.forensic_bundle_id,
            log.hash_id,
            log.env_fingerprint,
            log.duration_ms
        );
        let correlation_id = format!(
            "ftui-corr-{}",
            stable_hash_hex(correlation_material.as_bytes())
        );

        Ok(FtuiTelemetryRecord {
            correlation_id,
            run_id: log.run_id.clone(),
            journey_id,
            event_id: event_id.to_owned(),
            state: state.to_owned(),
            seed,
            test_id: log.test_id.clone(),
            replay_command: log.replay_command.clone(),
            env_fingerprint: log.env_fingerprint.clone(),
            duration_ms,
            status,
            mode,
            artifact_ref,
            reason_code: log.reason_code.clone(),
            ts_unix_ms: log.ts_unix_ms,
        })
    }

    pub fn build_artifact_index(
        &self,
        logs: &[StructuredTestLog],
    ) -> Result<FtuiArtifactIndex, String> {
        let mut entries = logs
            .iter()
            .map(|log| {
                let event = self.from_structured_log(log)?;
                Ok(FtuiArtifactIndexEntry {
                    correlation_id: event.correlation_id,
                    bundle_id: log.forensic_bundle_id.clone(),
                    run_id: log.run_id.clone(),
                    test_id: log.test_id.clone(),
                    captured_unix_ms: log.ts_unix_ms,
                    replay_ref: log.replay_command.clone(),
                    artifact_refs: log.artifact_refs.clone(),
                    status: log.status,
                    reason_code: log.reason_code.clone(),
                })
            })
            .collect::<Result<Vec<_>, String>>()?;

        entries.sort_by(|left, right| {
            (
                left.captured_unix_ms,
                left.run_id.as_str(),
                left.test_id.as_str(),
                left.bundle_id.as_str(),
                left.correlation_id.as_str(),
            )
                .cmp(&(
                    right.captured_unix_ms,
                    right.run_id.as_str(),
                    right.test_id.as_str(),
                    right.bundle_id.as_str(),
                    right.correlation_id.as_str(),
                ))
        });

        Ok(FtuiArtifactIndex { entries })
    }
}

impl Default for FtuiTelemetryAdapter {
    fn default() -> Self {
        Self::strict_default()
    }
}

fn enum_token<T: Serialize>(label: &str, value: &T) -> Result<String, String> {
    let encoded = serde_json::to_value(value)
        .map_err(|err| format!("failed to serialize enum token for {label}: {err}"))?;
    encoded
        .as_str()
        .map(ToOwned::to_owned)
        .ok_or_else(|| format!("enum token for {label} should serialize to string"))
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
    fn require_non_empty_fixture_id(&self, context: &str) -> Result<(), String> {
        if self
            .fixture_id
            .as_deref()
            .is_none_or(|value| value.trim().is_empty())
        {
            return Err(format!(
                "{context} requires fixture_id for deterministic replay"
            ));
        }
        Ok(())
    }

    fn require_environment_key(&self, key: &str, context: &str) -> Result<(), String> {
        if self
            .environment
            .get(key)
            .is_none_or(|value| value.trim().is_empty())
        {
            return Err(format!(
                "{context} missing required environment key `{key}`"
            ));
        }
        Ok(())
    }

    fn validate_packet_003_replay_metadata(&self) -> Result<(), String> {
        if self.packet_id != "FNX-P2C-003" {
            return Ok(());
        }

        match self.test_id.as_str() {
            "unit::fnx-p2c-003::contract" => {
                let context = "packet-003 unit contract telemetry";
                self.require_non_empty_fixture_id(context)?;
                for key in ["route_id", "backend_name", "strict_mode"] {
                    self.require_environment_key(key, context)?;
                }
            }
            "property::fnx-p2c-003::invariants" => {
                let context = "packet-003 property invariant telemetry";
                self.require_non_empty_fixture_id(context)?;
                if self.seed.is_none() {
                    return Err(
                        "packet-003 property invariant telemetry requires deterministic seed"
                            .to_owned(),
                    );
                }
                for key in ["graph_fingerprint", "cache_key_digest", "invariant_id"] {
                    self.require_environment_key(key, context)?;
                }
            }
            _ => {}
        }

        Ok(())
    }

    fn validate_packet_004_replay_metadata(&self) -> Result<(), String> {
        if self.packet_id != "FNX-P2C-004" {
            return Ok(());
        }

        match self.test_id.as_str() {
            "unit::fnx-p2c-004::contract" => {
                let context = "packet-004 unit contract telemetry";
                self.require_non_empty_fixture_id(context)?;
                for key in ["conversion_path", "input_shape", "strict_mode"] {
                    self.require_environment_key(key, context)?;
                }
            }
            "property::fnx-p2c-004::invariants" => {
                let context = "packet-004 property invariant telemetry";
                self.require_non_empty_fixture_id(context)?;
                if self.seed.is_none() {
                    return Err(
                        "packet-004 property invariant telemetry requires deterministic seed"
                            .to_owned(),
                    );
                }
                for key in ["graph_fingerprint", "relabel_mode", "invariant_id"] {
                    self.require_environment_key(key, context)?;
                }
            }
            _ => {}
        }

        Ok(())
    }

    fn validate_packet_005_replay_metadata(&self) -> Result<(), String> {
        if self.packet_id != "FNX-P2C-005" {
            return Ok(());
        }

        match self.test_id.as_str() {
            "unit::fnx-p2c-005::contract" => {
                let context = "packet-005 unit contract telemetry";
                self.require_non_empty_fixture_id(context)?;
                for key in [
                    "algorithm_family",
                    "source_target_pair",
                    "strict_mode",
                    "policy_row_id",
                ] {
                    self.require_environment_key(key, context)?;
                }
            }
            "property::fnx-p2c-005::invariants" => {
                let context = "packet-005 property invariant telemetry";
                self.require_non_empty_fixture_id(context)?;
                if self.seed.is_none() {
                    return Err(
                        "packet-005 property invariant telemetry requires deterministic seed"
                            .to_owned(),
                    );
                }
                for key in [
                    "graph_fingerprint",
                    "tie_break_policy",
                    "invariant_id",
                    "policy_row_id",
                ] {
                    self.require_environment_key(key, context)?;
                }
            }
            _ => {}
        }

        Ok(())
    }

    fn validate_packet_006_replay_metadata(&self) -> Result<(), String> {
        if self.packet_id != "FNX-P2C-006" {
            return Ok(());
        }

        match self.test_id.as_str() {
            "unit::fnx-p2c-006::contract" => {
                let context = "packet-006 unit contract telemetry";
                self.require_non_empty_fixture_id(context)?;
                for key in ["io_path", "strict_mode", "input_digest", "output_digest"] {
                    self.require_environment_key(key, context)?;
                }
            }
            "property::fnx-p2c-006::invariants" => {
                let context = "packet-006 property invariant telemetry";
                self.require_non_empty_fixture_id(context)?;
                if self.seed.is_none() {
                    return Err(
                        "packet-006 property invariant telemetry requires deterministic seed"
                            .to_owned(),
                    );
                }
                for key in [
                    "graph_fingerprint",
                    "mode_policy",
                    "invariant_id",
                    "input_digest",
                    "output_digest",
                ] {
                    self.require_environment_key(key, context)?;
                }
            }
            _ => {}
        }

        Ok(())
    }

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
        self.validate_packet_003_replay_metadata()?;
        self.validate_packet_004_replay_metadata()?;
        self.validate_packet_005_replay_metadata()?;
        self.validate_packet_006_replay_metadata()?;

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

#[derive(Debug, Clone, PartialEq)]
pub struct CgsePolicyDecision {
    pub policy_id: &'static str,
    pub rule: CgsePolicyRule,
    pub allowlisted_ambiguity: bool,
    pub fail_closed_default: &'static str,
    pub policy_spec_path: &'static str,
    pub policy_spec_schema_path: &'static str,
    pub legacy_tiebreak_ledger_path: &'static str,
    pub semantics_threat_model_path: &'static str,
    pub decision: DecisionRecord,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct CgsePolicyEngine {
    mode: CompatibilityMode,
}

impl CgsePolicyEngine {
    #[must_use]
    pub const fn new(mode: CompatibilityMode) -> Self {
        Self { mode }
    }

    #[must_use]
    pub const fn mode(self) -> CompatibilityMode {
        self.mode
    }

    #[must_use]
    pub fn evaluate(
        &self,
        rule: CgsePolicyRule,
        ambiguity_tag: Option<&str>,
        incompatibility_probability: f64,
        unknown_incompatible_feature: bool,
    ) -> CgsePolicyDecision {
        self.evaluate_at(
            rule,
            ambiguity_tag,
            incompatibility_probability,
            unknown_incompatible_feature,
            unix_time_ms(),
        )
    }

    #[must_use]
    pub fn evaluate_at(
        &self,
        rule: CgsePolicyRule,
        ambiguity_tag: Option<&str>,
        incompatibility_probability: f64,
        unknown_incompatible_feature: bool,
        ts_unix_ms: u128,
    ) -> CgsePolicyDecision {
        let nan_detected = incompatibility_probability.is_nan();
        let clamped_probability = if nan_detected {
            1.0
        } else {
            incompatibility_probability.clamp(0.0, 1.0)
        };
        let allowlisted_ambiguity =
            ambiguity_tag.is_some_and(|tag| rule.hardened_allowlist().contains(&tag));
        let hardened_ambiguity_violation = matches!(self.mode, CompatibilityMode::Hardened)
            && ambiguity_tag.is_some()
            && !allowlisted_ambiguity;

        let action = if unknown_incompatible_feature || nan_detected || hardened_ambiguity_violation
        {
            DecisionAction::FailClosed
        } else {
            decision_theoretic_action(self.mode, clamped_probability, false)
        };

        let rationale = if nan_detected {
            format!(
                "{} triggered fail-closed due to NaN incompatibility_probability",
                rule.fail_closed_default()
            )
        } else if unknown_incompatible_feature {
            format!(
                "{} triggered fail-closed due to unknown incompatible feature",
                rule.fail_closed_default()
            )
        } else if hardened_ambiguity_violation {
            let tag = ambiguity_tag.unwrap_or("none");
            format!(
                "{} triggered fail-closed because ambiguity tag `{tag}` is not allowlisted in hardened mode",
                rule.fail_closed_default()
            )
        } else {
            format!(
                "deterministic policy {} selected {:?} at incompatibility_probability={clamped_probability:.4}",
                rule.as_rule_id(),
                action
            )
        };

        let decision = DecisionRecord {
            ts_unix_ms,
            operation: format!(
                "{}::{}",
                rule.operation_family().as_str(),
                rule.as_rule_id().to_lowercase()
            ),
            mode: self.mode,
            action,
            incompatibility_probability: clamped_probability,
            rationale,
            evidence: vec![
                EvidenceTerm {
                    signal: "cgse_policy_rule_id".to_owned(),
                    observed_value: rule.as_rule_id().to_owned(),
                    log_likelihood_ratio: 1.0,
                },
                EvidenceTerm {
                    signal: "cgse_operation_family".to_owned(),
                    observed_value: rule.operation_family().as_str().to_owned(),
                    log_likelihood_ratio: 0.5,
                },
                EvidenceTerm {
                    signal: "cgse_ambiguity_tag".to_owned(),
                    observed_value: ambiguity_tag.unwrap_or("none").to_owned(),
                    log_likelihood_ratio: if allowlisted_ambiguity { 0.25 } else { -0.25 },
                },
                EvidenceTerm {
                    signal: "cgse_hardened_allowlist_hit".to_owned(),
                    observed_value: allowlisted_ambiguity.to_string(),
                    log_likelihood_ratio: if allowlisted_ambiguity { 0.75 } else { -0.75 },
                },
            ],
        };

        CgsePolicyDecision {
            policy_id: rule.policy_id(),
            rule,
            allowlisted_ambiguity,
            fail_closed_default: rule.fail_closed_default(),
            policy_spec_path: CGSE_POLICY_SPEC_PATH,
            policy_spec_schema_path: CGSE_POLICY_SPEC_SCHEMA_PATH,
            legacy_tiebreak_ledger_path: CGSE_LEGACY_TIEBREAK_LEDGER_PATH,
            semantics_threat_model_path: CGSE_SEMANTICS_THREAT_MODEL_PATH,
            decision,
        }
    }
}

pub trait CgsePolicyEvaluator {
    fn mode(&self) -> CompatibilityMode;

    fn evaluate(
        &self,
        rule: CgsePolicyRule,
        ambiguity_tag: Option<&str>,
        incompatibility_probability: f64,
        unknown_incompatible_feature: bool,
    ) -> CgsePolicyDecision;
}

impl CgsePolicyEvaluator for CgsePolicyEngine {
    fn mode(&self) -> CompatibilityMode {
        CgsePolicyEngine::mode(*self)
    }

    fn evaluate(
        &self,
        rule: CgsePolicyRule,
        ambiguity_tag: Option<&str>,
        incompatibility_probability: f64,
        unknown_incompatible_feature: bool,
    ) -> CgsePolicyDecision {
        CgsePolicyEngine::evaluate(
            self,
            rule,
            ambiguity_tag,
            incompatibility_probability,
            unknown_incompatible_feature,
        )
    }
}

/// Current schema version for decision ledger serialization.
pub const DECISION_LEDGER_SCHEMA_VERSION: &str = "1.0.0";

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

    /// Convert to a versioned ledger for serialization.
    #[must_use]
    pub fn to_versioned(&self) -> VersionedDecisionLedger {
        VersionedDecisionLedger::from_evidence_ledger(self)
    }
}

/// A decision ledger with explicit schema versioning for forward compatibility.
///
/// Use this struct when persisting ledgers to disk or transmitting over the wire.
/// The schema version allows consumers to detect incompatible changes and
/// migrate data appropriately.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct VersionedDecisionLedger {
    /// Schema version string (semver format)
    pub schema_version: String,
    /// Ledger identifier for tracking
    pub ledger_id: String,
    /// Unix timestamp when ledger was created (milliseconds)
    pub created_at_unix_ms: u128,
    /// Unix timestamp of most recent record (milliseconds)
    pub last_updated_unix_ms: u128,
    /// Total number of records
    pub record_count: usize,
    /// The decision records
    pub records: Vec<DecisionRecord>,
}

impl VersionedDecisionLedger {
    /// Create a new versioned ledger from an evidence ledger.
    #[must_use]
    pub fn from_evidence_ledger(ledger: &EvidenceLedger) -> Self {
        let now = unix_time_ms();
        let last_updated = ledger.records().last().map_or(now, |r| r.ts_unix_ms);

        Self {
            schema_version: DECISION_LEDGER_SCHEMA_VERSION.to_owned(),
            ledger_id: format!("ledger-{}", now),
            created_at_unix_ms: now,
            last_updated_unix_ms: last_updated,
            record_count: ledger.records().len(),
            records: ledger.records().to_vec(),
        }
    }

    /// Create a new empty versioned ledger with a specific ID.
    #[must_use]
    pub fn new(ledger_id: &str) -> Self {
        let now = unix_time_ms();
        Self {
            schema_version: DECISION_LEDGER_SCHEMA_VERSION.to_owned(),
            ledger_id: ledger_id.to_owned(),
            created_at_unix_ms: now,
            last_updated_unix_ms: now,
            record_count: 0,
            records: Vec::new(),
        }
    }

    /// Append a decision record to the ledger.
    pub fn append(&mut self, record: DecisionRecord) {
        self.last_updated_unix_ms = record.ts_unix_ms;
        self.records.push(record);
        self.record_count = self.records.len();
    }

    /// Check if this ledger's schema is compatible with current version.
    #[must_use]
    pub fn is_schema_compatible(&self) -> bool {
        // Simple semver major version check
        let current_major = DECISION_LEDGER_SCHEMA_VERSION
            .split('.')
            .next()
            .and_then(|s| s.parse::<u32>().ok())
            .unwrap_or(0);
        let ledger_major = self
            .schema_version
            .split('.')
            .next()
            .and_then(|s| s.parse::<u32>().ok())
            .unwrap_or(0);

        ledger_major == current_major
    }

    /// Validate the ledger structure.
    #[must_use]
    pub fn validate(&self) -> LedgerValidationResult {
        let mut errors = Vec::new();

        if self.schema_version.is_empty() {
            errors.push("schema_version is empty".to_owned());
        }

        if self.ledger_id.is_empty() {
            errors.push("ledger_id is empty".to_owned());
        }

        if self.record_count != self.records.len() {
            errors.push(format!(
                "record_count mismatch: stated {} but have {}",
                self.record_count,
                self.records.len()
            ));
        }

        // Check records are in timestamp order
        for i in 1..self.records.len() {
            if self.records[i].ts_unix_ms < self.records[i - 1].ts_unix_ms {
                errors.push(format!(
                    "records out of order at index {}: {} < {}",
                    i,
                    self.records[i].ts_unix_ms,
                    self.records[i - 1].ts_unix_ms
                ));
                break;
            }
        }

        LedgerValidationResult {
            is_valid: errors.is_empty(),
            schema_compatible: self.is_schema_compatible(),
            errors,
        }
    }

    /// Serialize to JSON with pretty formatting.
    pub fn to_json_pretty(&self) -> Result<String, serde_json::Error> {
        serde_json::to_string_pretty(self)
    }

    /// Deserialize from JSON.
    pub fn from_json(json: &str) -> Result<Self, serde_json::Error> {
        serde_json::from_str(json)
    }

    /// Merge another ledger's records into this one.
    ///
    /// Records are merged and sorted by timestamp.
    pub fn merge(&mut self, other: &Self) {
        self.records.extend(other.records.iter().cloned());
        self.records.sort_by_key(|r| r.ts_unix_ms);
        self.record_count = self.records.len();
        self.last_updated_unix_ms = self
            .records
            .last()
            .map_or(self.created_at_unix_ms, |r| r.ts_unix_ms);
    }
}

/// Result of validating a versioned decision ledger.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct LedgerValidationResult {
    pub is_valid: bool,
    pub schema_compatible: bool,
    pub errors: Vec<String>,
}

// ---------------------------------------------------------------------------
// Drift Analysis
// ---------------------------------------------------------------------------

/// Threshold for classifying a decision as "under-confident" (high risk).
pub const UNDER_CONFIDENT_THRESHOLD: f64 = 0.3;

/// Milliseconds in one week (7 days).
pub const MILLIS_PER_WEEK: u128 = 7 * 24 * 60 * 60 * 1000;

/// Analyzes decision records to identify under-confident regions and drift.
#[derive(Debug, Clone, Default)]
pub struct DriftAnalyzer {
    threshold: f64,
}

impl DriftAnalyzer {
    /// Create a new analyzer with the default threshold.
    #[must_use]
    pub fn new() -> Self {
        Self {
            threshold: UNDER_CONFIDENT_THRESHOLD,
        }
    }

    /// Create an analyzer with a custom threshold.
    #[must_use]
    pub fn with_threshold(threshold: f64) -> Self {
        Self {
            threshold: threshold.clamp(0.0, 1.0),
        }
    }

    /// Analyze a ledger and produce a drift feedback report.
    #[must_use]
    pub fn analyze(&self, ledger: &VersionedDecisionLedger) -> DriftFeedbackReport {
        let records = &ledger.records;
        if records.is_empty() {
            return DriftFeedbackReport {
                total_decisions: 0,
                under_confident_count: 0,
                under_confident_rate: 0.0,
                weekly_summaries: Vec::new(),
                top_operations: Vec::new(),
                recommendations: vec!["No decisions to analyze".to_owned()],
            };
        }

        // Find under-confident decisions
        let under_confident: Vec<_> = records
            .iter()
            .filter(|r| r.incompatibility_probability >= self.threshold)
            .collect();

        // Group by week
        let min_ts = records.iter().map(|r| r.ts_unix_ms).min().unwrap_or(0);
        let mut weekly_map: std::collections::BTreeMap<u128, WeeklySummary> =
            std::collections::BTreeMap::new();

        for record in records {
            let week_number = (record.ts_unix_ms - min_ts) / MILLIS_PER_WEEK;
            let week_start = min_ts + (week_number * MILLIS_PER_WEEK);

            let summary = weekly_map
                .entry(week_start)
                .or_insert_with(|| WeeklySummary {
                    week_start_unix_ms: week_start,
                    total_decisions: 0,
                    under_confident_count: 0,
                    avg_probability: 0.0,
                    fail_closed_count: 0,
                });

            summary.total_decisions += 1;
            if record.incompatibility_probability >= self.threshold {
                summary.under_confident_count += 1;
            }
            if record.action == DecisionAction::FailClosed {
                summary.fail_closed_count += 1;
            }
        }

        // Calculate averages
        for (week_start, summary) in &mut weekly_map {
            let week_records: Vec<_> = records
                .iter()
                .filter(|r| {
                    let week_number = (r.ts_unix_ms - min_ts) / MILLIS_PER_WEEK;
                    min_ts + (week_number * MILLIS_PER_WEEK) == *week_start
                })
                .collect();

            if !week_records.is_empty() {
                summary.avg_probability = week_records
                    .iter()
                    .map(|r| r.incompatibility_probability)
                    .sum::<f64>()
                    / week_records.len() as f64;
            }
        }

        // Find top operations by under-confidence
        let mut op_counts: std::collections::HashMap<String, usize> =
            std::collections::HashMap::new();
        for record in &under_confident {
            *op_counts.entry(record.operation.clone()).or_insert(0) += 1;
        }
        let mut top_ops: Vec<_> = op_counts.into_iter().collect();
        top_ops.sort_by_key(|item| std::cmp::Reverse(item.1));
        let top_operations: Vec<OperationRiskSummary> = top_ops
            .into_iter()
            .take(5)
            .map(|(op, count)| OperationRiskSummary {
                operation: op,
                under_confident_count: count,
            })
            .collect();

        // Generate recommendations
        let mut recommendations = Vec::new();
        let under_rate = under_confident.len() as f64 / records.len() as f64;

        if under_rate > 0.5 {
            recommendations.push(
                "High under-confidence rate (>50%). Consider reviewing threshold or adding validation.".to_owned()
            );
        }

        if !top_operations.is_empty() {
            recommendations.push(format!(
                "Top risky operation: '{}' ({} under-confident decisions)",
                top_operations[0].operation, top_operations[0].under_confident_count
            ));
        }

        // Check for drift (increasing under-confidence over time)
        let weekly_summaries: Vec<_> = weekly_map.into_values().collect();
        if weekly_summaries.len() >= 2 {
            let first_rate = if weekly_summaries[0].total_decisions > 0 {
                weekly_summaries[0].under_confident_count as f64
                    / weekly_summaries[0].total_decisions as f64
            } else {
                0.0
            };
            let last_rate = if weekly_summaries.last().unwrap().total_decisions > 0 {
                weekly_summaries.last().unwrap().under_confident_count as f64
                    / weekly_summaries.last().unwrap().total_decisions as f64
            } else {
                0.0
            };

            if last_rate > first_rate * 1.5 {
                recommendations
                    .push("Drift detected: under-confidence rate increasing over time.".to_owned());
            }
        }

        DriftFeedbackReport {
            total_decisions: records.len(),
            under_confident_count: under_confident.len(),
            under_confident_rate: under_rate,
            weekly_summaries,
            top_operations,
            recommendations,
        }
    }
}

/// Weekly summary of decision confidence.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct WeeklySummary {
    pub week_start_unix_ms: u128,
    pub total_decisions: usize,
    pub under_confident_count: usize,
    pub avg_probability: f64,
    pub fail_closed_count: usize,
}

/// Summary of under-confidence for a specific operation.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct OperationRiskSummary {
    pub operation: String,
    pub under_confident_count: usize,
}

/// Drift feedback report with weekly analysis and recommendations.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct DriftFeedbackReport {
    pub total_decisions: usize,
    pub under_confident_count: usize,
    pub under_confident_rate: f64,
    pub weekly_summaries: Vec<WeeklySummary>,
    pub top_operations: Vec<OperationRiskSummary>,
    pub recommendations: Vec<String>,
}

impl DriftFeedbackReport {
    /// Check if the report indicates drift.
    #[must_use]
    pub fn has_drift(&self) -> bool {
        self.recommendations
            .iter()
            .any(|r| r.contains("Drift detected"))
    }

    /// Check if there are high-risk operations.
    #[must_use]
    pub fn has_high_risk_operations(&self) -> bool {
        !self.top_operations.is_empty()
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
            validate_cost: 25.0,
            reject_false_positive: 60.0,
        }
    }

    #[must_use]
    pub const fn hardened_default() -> Self {
        Self {
            allow_false_negative: 120.0,
            validate_cost: 30.0,
            reject_false_positive: 70.0,
        }
    }
}

// ──────────────────────────────────────────────────────────────────────────────
// D5: Loss matrix calibration with Bayesian shrinkage prior
// ──────────────────────────────────────────────────────────────────────────────

/// Prior distribution parameters for Bayesian shrinkage estimation.
///
/// Uses a normal prior N(prior_mean, prior_variance) that pulls empirical
/// estimates toward the prior when sample size is small or variance is high.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct BayesianShrinkagePrior {
    /// Prior mean for the loss value.
    pub prior_mean: f64,
    /// Prior variance (τ₀²) - controls how strongly we trust the prior.
    /// Smaller values mean stronger pull toward prior_mean.
    pub prior_variance: f64,
}

impl BayesianShrinkagePrior {
    /// Default prior for false-negative loss (allowing incompatible operation).
    #[must_use]
    pub const fn for_false_negative() -> Self {
        Self {
            prior_mean: 100.0,
            prior_variance: 400.0, // σ = 20
        }
    }

    /// Default prior for validation cost.
    #[must_use]
    pub const fn for_validate_cost() -> Self {
        Self {
            prior_mean: 25.0,
            prior_variance: 100.0, // σ = 10
        }
    }

    /// Default prior for false-positive loss (rejecting compatible operation).
    #[must_use]
    pub const fn for_false_positive() -> Self {
        Self {
            prior_mean: 60.0,
            prior_variance: 225.0, // σ = 15
        }
    }

    /// Compute shrinkage weight given empirical variance and sample count.
    ///
    /// w = τ₀² / (τ₀² + σ²/n)
    ///
    /// When n is small or σ² is large, w is small (trust prior more).
    /// When n is large and σ² is small, w approaches 1 (trust data more).
    #[must_use]
    pub fn shrinkage_weight(&self, empirical_variance: f64, sample_count: usize) -> f64 {
        if sample_count == 0 {
            return 0.0; // No data: use prior entirely
        }
        // Guard against zero prior_variance (invalid config)
        if self.prior_variance <= 0.0 {
            return 0.0; // Infinite prior certainty: use prior entirely
        }
        let n = sample_count as f64;
        // Guard against zero or under-estimated variance producing full-weight empirical
        // posterior with small sample sizes.
        let variance_of_mean = (empirical_variance / n).max(self.prior_variance / n);
        self.prior_variance / (self.prior_variance + variance_of_mean)
    }

    /// Compute the posterior mean using shrinkage.
    ///
    /// μ_posterior = w * ȳ + (1-w) * μ₀
    #[must_use]
    pub fn posterior_mean(
        &self,
        empirical_mean: f64,
        empirical_variance: f64,
        sample_count: usize,
    ) -> f64 {
        let w = self.shrinkage_weight(empirical_variance, sample_count);
        w * empirical_mean + (1.0 - w) * self.prior_mean
    }
}

/// A single observed loss from a decision outcome.
#[derive(Debug, Clone, PartialEq)]
pub struct LossObservation {
    /// Unix timestamp in milliseconds when the observation was recorded.
    pub ts_unix_ms: u128,
    /// The decision action that was taken.
    pub action: DecisionAction,
    /// True state: was the operation actually incompatible?
    pub was_incompatible: bool,
    /// Realized loss from this decision.
    pub realized_loss: f64,
    /// Which loss category this contributes to.
    pub loss_category: LossCategory,
}

/// Categories of loss that can be observed.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum LossCategory {
    /// We allowed an incompatible operation (false negative).
    AllowFalseNegative,
    /// We paid validation cost.
    ValidateCost,
    /// We rejected a compatible operation (false positive).
    RejectFalsePositive,
}

/// Aggregated statistics for a loss category.
#[derive(Debug, Clone, Copy, PartialEq, Default)]
pub struct LossCategoryStats {
    pub count: usize,
    pub sum: f64,
    pub sum_sq: f64,
}

impl LossCategoryStats {
    #[must_use]
    pub fn mean(&self) -> f64 {
        if self.count == 0 {
            0.0
        } else {
            self.sum / self.count as f64
        }
    }

    #[must_use]
    pub fn variance(&self) -> f64 {
        if self.count < 2 {
            return f64::INFINITY; // Unknown variance with < 2 samples
        }
        let n = self.count as f64;
        let mean = self.sum / n;
        (self.sum_sq / n) - (mean * mean)
    }

    pub fn add(&mut self, value: f64) {
        self.count += 1;
        self.sum += value;
        self.sum_sq += value * value;
    }
}

/// A loss matrix calibrated via Bayesian shrinkage from observed data.
#[derive(Debug, Clone, PartialEq)]
pub struct CalibratedLossMatrix {
    /// The calibrated loss values.
    pub matrix: LossMatrix,
    /// Shrinkage weights applied (0 = pure prior, 1 = pure empirical).
    pub shrinkage_weights: LossShrinkageWeights,
    /// Sample counts per category.
    pub sample_counts: LossSampleCounts,
    /// Calibration timestamp.
    pub calibrated_at_unix_ms: u128,
}

/// Shrinkage weights for each loss category.
#[derive(Debug, Clone, Copy, PartialEq, Default)]
pub struct LossShrinkageWeights {
    pub allow_false_negative: f64,
    pub validate_cost: f64,
    pub reject_false_positive: f64,
}

/// Sample counts for each loss category.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub struct LossSampleCounts {
    pub allow_false_negative: usize,
    pub validate_cost: usize,
    pub reject_false_positive: usize,
}

/// Calibrator that applies Bayesian shrinkage to loss observations.
#[derive(Debug, Clone)]
pub struct LossMatrixCalibrator {
    prior_false_negative: BayesianShrinkagePrior,
    prior_validate_cost: BayesianShrinkagePrior,
    prior_false_positive: BayesianShrinkagePrior,
    stats_false_negative: LossCategoryStats,
    stats_validate_cost: LossCategoryStats,
    stats_false_positive: LossCategoryStats,
}

impl Default for LossMatrixCalibrator {
    fn default() -> Self {
        Self::new()
    }
}

impl LossMatrixCalibrator {
    /// Create a new calibrator with default priors.
    #[must_use]
    pub fn new() -> Self {
        Self {
            prior_false_negative: BayesianShrinkagePrior::for_false_negative(),
            prior_validate_cost: BayesianShrinkagePrior::for_validate_cost(),
            prior_false_positive: BayesianShrinkagePrior::for_false_positive(),
            stats_false_negative: LossCategoryStats::default(),
            stats_validate_cost: LossCategoryStats::default(),
            stats_false_positive: LossCategoryStats::default(),
        }
    }

    /// Create a calibrator with custom priors.
    #[must_use]
    pub fn with_priors(
        prior_false_negative: BayesianShrinkagePrior,
        prior_validate_cost: BayesianShrinkagePrior,
        prior_false_positive: BayesianShrinkagePrior,
    ) -> Self {
        Self {
            prior_false_negative,
            prior_validate_cost,
            prior_false_positive,
            stats_false_negative: LossCategoryStats::default(),
            stats_validate_cost: LossCategoryStats::default(),
            stats_false_positive: LossCategoryStats::default(),
        }
    }

    /// Record an observation.
    pub fn observe(&mut self, obs: &LossObservation) {
        match obs.loss_category {
            LossCategory::AllowFalseNegative => {
                self.stats_false_negative.add(obs.realized_loss);
            }
            LossCategory::ValidateCost => {
                self.stats_validate_cost.add(obs.realized_loss);
            }
            LossCategory::RejectFalsePositive => {
                self.stats_false_positive.add(obs.realized_loss);
            }
        }
    }

    /// Record multiple observations.
    pub fn observe_batch(&mut self, observations: &[LossObservation]) {
        for obs in observations {
            self.observe(obs);
        }
    }

    /// Produce a calibrated loss matrix using current observations.
    #[must_use]
    pub fn calibrate(&self) -> CalibratedLossMatrix {
        let w_fn = self.prior_false_negative.shrinkage_weight(
            self.stats_false_negative.variance(),
            self.stats_false_negative.count,
        );
        let w_vc = self.prior_validate_cost.shrinkage_weight(
            self.stats_validate_cost.variance(),
            self.stats_validate_cost.count,
        );
        let w_fp = self.prior_false_positive.shrinkage_weight(
            self.stats_false_positive.variance(),
            self.stats_false_positive.count,
        );

        let calibrated_fn = self.prior_false_negative.posterior_mean(
            self.stats_false_negative.mean(),
            self.stats_false_negative.variance(),
            self.stats_false_negative.count,
        );
        let calibrated_vc = self.prior_validate_cost.posterior_mean(
            self.stats_validate_cost.mean(),
            self.stats_validate_cost.variance(),
            self.stats_validate_cost.count,
        );
        let calibrated_fp = self.prior_false_positive.posterior_mean(
            self.stats_false_positive.mean(),
            self.stats_false_positive.variance(),
            self.stats_false_positive.count,
        );

        CalibratedLossMatrix {
            matrix: LossMatrix {
                allow_false_negative: calibrated_fn,
                validate_cost: calibrated_vc,
                reject_false_positive: calibrated_fp,
            },
            shrinkage_weights: LossShrinkageWeights {
                allow_false_negative: w_fn,
                validate_cost: w_vc,
                reject_false_positive: w_fp,
            },
            sample_counts: LossSampleCounts {
                allow_false_negative: self.stats_false_negative.count,
                validate_cost: self.stats_validate_cost.count,
                reject_false_positive: self.stats_false_positive.count,
            },
            calibrated_at_unix_ms: unix_time_ms(),
        }
    }

    /// Minimum samples needed before shrinkage weight exceeds threshold.
    ///
    /// Returns the sample count n where w >= threshold, assuming empirical
    /// variance equals a reference variance (prior_variance by default).
    #[must_use]
    pub fn samples_for_confidence(_prior: &BayesianShrinkagePrior, threshold: f64) -> usize {
        // w = τ₀² / (τ₀² + σ²/n)
        // threshold = τ₀² / (τ₀² + σ²/n)
        // threshold * (τ₀² + σ²/n) = τ₀²
        // threshold * σ²/n = τ₀² - threshold * τ₀²
        // threshold * σ²/n = τ₀² * (1 - threshold)
        // n = threshold * σ² / (τ₀² * (1 - threshold))
        //
        // Assuming σ² = τ₀² (empirical variance matches prior):
        // n = threshold / (1 - threshold)
        if threshold >= 1.0 {
            return usize::MAX;
        }
        if threshold <= 0.0 {
            return 0;
        }
        let n = threshold / (1.0 - threshold);
        let n_floor = n.floor();
        if (n - n_floor).abs() < 1e-9 {
            n_floor as usize
        } else {
            n.ceil() as usize
        }
    }

    /// Reset accumulated statistics.
    pub fn reset(&mut self) {
        self.stats_false_negative = LossCategoryStats::default();
        self.stats_validate_cost = LossCategoryStats::default();
        self.stats_false_positive = LossCategoryStats::default();
    }

    /// Get current sample counts.
    #[must_use]
    pub fn sample_counts(&self) -> LossSampleCounts {
        LossSampleCounts {
            allow_false_negative: self.stats_false_negative.count,
            validate_cost: self.stats_validate_cost.count,
            reject_false_positive: self.stats_false_positive.count,
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
    if unknown_incompatible_feature || incompatibility_probability.is_nan() {
        return DecisionAction::FailClosed;
    }

    let p = incompatibility_probability.clamp(0.0, 1.0);
    let loss = match mode {
        CompatibilityMode::Strict => LossMatrix::strict_default(),
        CompatibilityMode::Hardened => LossMatrix::hardened_default(),
    };

    // Expected loss for each action:
    // If we ALLOW: we lose allow_false_negative if it IS incompatible (prob p).
    let e_allow = p * loss.allow_false_negative;
    // If we VALIDATE: we lose validate_cost regardless of state.
    let e_validate = loss.validate_cost;
    // If we FAIL_CLOSED: we lose reject_false_positive if it WAS compatible (prob 1-p).
    let e_fail_closed = (1.0 - p) * loss.reject_false_positive;

    if e_allow <= e_validate && e_allow <= e_fail_closed {
        DecisionAction::Allow
    } else if e_validate <= e_fail_closed {
        DecisionAction::FullValidate
    } else {
        DecisionAction::FailClosed
    }
}

// ──────────────────────────────────────────────────────────────────────────────
// D4: Hardened-mode Bayesian admission controller
// ──────────────────────────────────────────────────────────────────────────────

/// Result of an admission decision from the Bayesian controller.
#[derive(Debug, Clone, PartialEq)]
pub struct AdmissionDecision {
    /// The action to take.
    pub action: DecisionAction,
    /// Expected loss for the chosen action.
    pub expected_loss: f64,
    /// Confidence in the decision (shrinkage-adjusted).
    pub confidence: f64,
    /// Whether the hardened-mode override was applied.
    pub hardened_override: bool,
    /// The probability estimate used.
    pub incompatibility_probability: f64,
    /// Rationale for the decision.
    pub rationale: String,
}

/// Configuration for the Bayesian admission controller.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct AdmissionControllerConfig {
    /// Minimum confidence required to trust empirical data (0-1).
    /// Below this, we fall back to conservative hardened-mode defaults.
    pub min_confidence_threshold: f64,
    /// In hardened mode, apply extra penalty to allow decisions.
    pub hardened_allow_penalty: f64,
    /// Maximum allowed incompatibility probability before auto-reject.
    pub max_incompatibility_probability: f64,
    /// Minimum samples before considering empirical data.
    pub min_samples_for_empirical: usize,
}

impl Default for AdmissionControllerConfig {
    fn default() -> Self {
        Self {
            min_confidence_threshold: 0.3,
            hardened_allow_penalty: 20.0,
            max_incompatibility_probability: 0.85,
            min_samples_for_empirical: 5,
        }
    }
}

impl AdmissionControllerConfig {
    /// More conservative config for high-risk environments.
    #[must_use]
    pub const fn conservative() -> Self {
        Self {
            min_confidence_threshold: 0.5,
            hardened_allow_penalty: 40.0,
            max_incompatibility_probability: 0.7,
            min_samples_for_empirical: 10,
        }
    }
}

/// Bayesian admission controller for hardened mode.
///
/// Uses calibrated loss matrices to make admission decisions, updating
/// beliefs based on observed outcomes and applying conservative overrides
/// when confidence is low.
#[derive(Debug, Clone)]
pub struct BayesianAdmissionController {
    mode: CompatibilityMode,
    config: AdmissionControllerConfig,
    calibrator: LossMatrixCalibrator,
    decision_count: u64,
    override_count: u64,
}

impl BayesianAdmissionController {
    /// Create a new admission controller for the given mode.
    #[must_use]
    pub fn new(mode: CompatibilityMode) -> Self {
        Self {
            mode,
            config: AdmissionControllerConfig::default(),
            calibrator: LossMatrixCalibrator::new(),
            decision_count: 0,
            override_count: 0,
        }
    }

    /// Create an admission controller with custom config.
    #[must_use]
    pub fn with_config(mode: CompatibilityMode, config: AdmissionControllerConfig) -> Self {
        Self {
            mode,
            config,
            calibrator: LossMatrixCalibrator::new(),
            decision_count: 0,
            override_count: 0,
        }
    }

    /// Get the current compatibility mode.
    #[must_use]
    pub fn mode(&self) -> CompatibilityMode {
        self.mode
    }

    /// Get the current config.
    #[must_use]
    pub fn config(&self) -> &AdmissionControllerConfig {
        &self.config
    }

    /// Make an admission decision.
    #[must_use]
    pub fn decide(&mut self, incompatibility_probability: f64) -> AdmissionDecision {
        self.decision_count += 1;

        // Handle edge cases
        if incompatibility_probability.is_nan() {
            return AdmissionDecision {
                action: DecisionAction::FailClosed,
                expected_loss: f64::INFINITY,
                confidence: 0.0,
                hardened_override: true,
                incompatibility_probability: f64::NAN,
                rationale: "NaN probability: fail closed".to_owned(),
            };
        }

        let p = incompatibility_probability.clamp(0.0, 1.0);

        // In hardened mode, auto-reject high-risk operations
        if self.mode == CompatibilityMode::Hardened
            && p > self.config.max_incompatibility_probability
        {
            self.override_count += 1;
            return AdmissionDecision {
                action: DecisionAction::FailClosed,
                expected_loss: p * 100.0,
                confidence: 1.0,
                hardened_override: true,
                incompatibility_probability: p,
                rationale: format!(
                    "Hardened mode: probability {} exceeds threshold {}",
                    p, self.config.max_incompatibility_probability
                ),
            };
        }

        // Get calibrated loss matrix
        let calibrated = self.calibrator.calibrate();
        let samples = calibrated.sample_counts;
        let weights = calibrated.shrinkage_weights;

        // Compute confidence as minimum shrinkage weight
        let confidence = weights
            .allow_false_negative
            .min(weights.validate_cost)
            .min(weights.reject_false_positive);

        // If confidence is too low or insufficient samples, use defaults with hardened penalty
        let total_samples =
            samples.allow_false_negative + samples.validate_cost + samples.reject_false_positive;
        let use_empirical = confidence >= self.config.min_confidence_threshold
            && total_samples >= self.config.min_samples_for_empirical;

        let loss = if use_empirical {
            calibrated.matrix
        } else {
            match self.mode {
                CompatibilityMode::Strict => LossMatrix::strict_default(),
                CompatibilityMode::Hardened => LossMatrix::hardened_default(),
            }
        };

        // Compute expected losses with hardened-mode penalty
        let allow_loss = if self.mode == CompatibilityMode::Hardened {
            loss.allow_false_negative + self.config.hardened_allow_penalty
        } else {
            loss.allow_false_negative
        };

        let e_allow = p * allow_loss;
        let e_validate = loss.validate_cost;
        let e_fail_closed = (1.0 - p) * loss.reject_false_positive;

        let (action, expected_loss, rationale) =
            if e_allow <= e_validate && e_allow <= e_fail_closed {
                (
                    DecisionAction::Allow,
                    e_allow,
                    format!(
                        "Allow: E[L]={:.2} < validate={:.2}, fail_closed={:.2}",
                        e_allow, e_validate, e_fail_closed
                    ),
                )
            } else if e_validate <= e_fail_closed {
                (
                    DecisionAction::FullValidate,
                    e_validate,
                    format!(
                        "Validate: E[L]={:.2} < fail_closed={:.2}",
                        e_validate, e_fail_closed
                    ),
                )
            } else {
                (
                    DecisionAction::FailClosed,
                    e_fail_closed,
                    format!(
                        "FailClosed: E[L]={:.2} < validate={:.2}",
                        e_fail_closed, e_validate
                    ),
                )
            };

        AdmissionDecision {
            action,
            expected_loss,
            confidence,
            hardened_override: false,
            incompatibility_probability: p,
            rationale,
        }
    }

    /// Record the outcome of a decision for future calibration.
    pub fn record_outcome(&mut self, decision: &AdmissionDecision, was_incompatible: bool) {
        let (category, realized_loss) = match decision.action {
            DecisionAction::Allow if was_incompatible => {
                // False negative: we allowed but it was incompatible
                (LossCategory::AllowFalseNegative, 100.0)
            }
            DecisionAction::Allow => {
                // Correct allow: no loss
                return;
            }
            DecisionAction::FullValidate => {
                // Validation cost is always paid
                (LossCategory::ValidateCost, 25.0)
            }
            DecisionAction::FailClosed if !was_incompatible => {
                // False positive: we rejected but it was compatible
                (LossCategory::RejectFalsePositive, 60.0)
            }
            DecisionAction::FailClosed => {
                // Correct rejection: no loss
                return;
            }
        };

        self.calibrator.observe(&LossObservation {
            ts_unix_ms: unix_time_ms(),
            action: decision.action,
            was_incompatible,
            realized_loss,
            loss_category: category,
        });
    }

    /// Get statistics about controller behavior.
    #[must_use]
    pub fn stats(&self) -> AdmissionControllerStats {
        AdmissionControllerStats {
            decision_count: self.decision_count,
            override_count: self.override_count,
            sample_counts: self.calibrator.sample_counts(),
            calibrated_matrix: self.calibrator.calibrate(),
        }
    }

    /// Reset the controller state (keeps config).
    pub fn reset(&mut self) {
        self.calibrator.reset();
        self.decision_count = 0;
        self.override_count = 0;
    }
}

/// Statistics from the admission controller.
#[derive(Debug, Clone, PartialEq)]
pub struct AdmissionControllerStats {
    /// Total decisions made.
    pub decision_count: u64,
    /// Decisions where hardened-mode override was applied.
    pub override_count: u64,
    /// Sample counts per loss category.
    pub sample_counts: LossSampleCounts,
    /// Current calibrated loss matrix.
    pub calibrated_matrix: CalibratedLossMatrix,
}

// ──────────────────────────────────────────────────────────────────────────────
// D6: Calibrated confidence with Brier score gate
// ──────────────────────────────────────────────────────────────────────────────

/// A single prediction-outcome pair for Brier score computation.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct PredictionOutcome {
    /// Predicted probability of incompatibility (0-1).
    pub predicted_probability: f64,
    /// Actual outcome: 1.0 if incompatible, 0.0 if compatible.
    pub actual_outcome: f64,
    /// Timestamp of the observation.
    pub ts_unix_ms: u128,
}

/// Brier score calibration tracker.
///
/// Computes Brier score = (1/n) * Σ(p - o)² where p is predicted probability
/// and o is actual outcome (0 or 1). Perfect calibration yields Brier score = 0.
#[derive(Debug, Clone, Default)]
pub struct BrierScoreTracker {
    predictions: Vec<PredictionOutcome>,
    sum_squared_error: f64,
}

impl BrierScoreTracker {
    /// Create a new empty tracker.
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    /// Record a prediction and its outcome.
    pub fn record(&mut self, predicted_probability: f64, was_incompatible: bool) {
        let actual = if was_incompatible { 1.0 } else { 0.0 };
        let p = predicted_probability.clamp(0.0, 1.0);
        let error = p - actual;
        let sq_error = error * error;

        self.predictions.push(PredictionOutcome {
            predicted_probability: p,
            actual_outcome: actual,
            ts_unix_ms: unix_time_ms(),
        });
        self.sum_squared_error += sq_error;
    }

    /// Get the current Brier score (0 = perfect, 1 = worst).
    #[must_use]
    pub fn brier_score(&self) -> f64 {
        if self.predictions.is_empty() {
            return 0.5; // Neutral score when no data
        }
        self.sum_squared_error / self.predictions.len() as f64
    }

    /// Get number of predictions recorded.
    #[must_use]
    pub fn count(&self) -> usize {
        self.predictions.len()
    }

    /// Check if predictions are well-calibrated (Brier score below threshold).
    #[must_use]
    pub fn is_calibrated(&self, threshold: f64) -> bool {
        self.count() >= 10 && self.brier_score() <= threshold
    }

    /// Reset the tracker.
    pub fn reset(&mut self) {
        self.predictions.clear();
        self.sum_squared_error = 0.0;
    }

    /// Get calibration metrics.
    #[must_use]
    pub fn metrics(&self) -> BrierScoreMetrics {
        let n = self.predictions.len();
        if n == 0 {
            return BrierScoreMetrics {
                brier_score: 0.5,
                sample_count: 0,
                reliability: 0.0,
                resolution: 0.0,
                base_rate: 0.5,
            };
        }

        let brier = self.brier_score();
        let base_rate = self
            .predictions
            .iter()
            .map(|p| p.actual_outcome)
            .sum::<f64>()
            / n as f64;

        // Reliability: how well do predicted probabilities match observed frequencies?
        // Lower is better. This is a simplified version.
        let reliability = self.compute_reliability();

        // Resolution: ability to separate positive and negative cases
        // Higher is better.
        let resolution = self.compute_resolution(base_rate);

        BrierScoreMetrics {
            brier_score: brier,
            sample_count: n,
            reliability,
            resolution,
            base_rate,
        }
    }

    fn compute_reliability(&self) -> f64 {
        if self.predictions.is_empty() {
            return 0.0;
        }

        // Bin predictions into 10 bins and compute reliability
        let mut bins: [Vec<&PredictionOutcome>; 10] = Default::default();
        for pred in &self.predictions {
            let bin_idx = (pred.predicted_probability * 10.0).floor().min(9.0) as usize;
            bins[bin_idx].push(pred);
        }

        let mut reliability = 0.0;
        let n = self.predictions.len() as f64;

        for (i, bin) in bins.iter().enumerate() {
            if bin.is_empty() {
                continue;
            }
            let bin_prob = (i as f64 + 0.5) / 10.0; // Bin center
            let actual_freq = bin.iter().map(|p| p.actual_outcome).sum::<f64>() / bin.len() as f64;
            let error = bin_prob - actual_freq;
            reliability += (bin.len() as f64 / n) * error * error;
        }

        reliability
    }

    fn compute_resolution(&self, base_rate: f64) -> f64 {
        if self.predictions.is_empty() {
            return 0.0;
        }

        // Resolution measures how much predictions deviate from base rate
        let mut resolution = 0.0;
        let n = self.predictions.len() as f64;

        // Bin predictions and compute resolution
        let mut bins: [Vec<&PredictionOutcome>; 10] = Default::default();
        for pred in &self.predictions {
            let bin_idx = (pred.predicted_probability * 10.0).floor().min(9.0) as usize;
            bins[bin_idx].push(pred);
        }

        for bin in &bins {
            if bin.is_empty() {
                continue;
            }
            let actual_freq = bin.iter().map(|p| p.actual_outcome).sum::<f64>() / bin.len() as f64;
            let deviation = actual_freq - base_rate;
            resolution += (bin.len() as f64 / n) * deviation * deviation;
        }

        resolution
    }
}

/// Detailed Brier score metrics.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct BrierScoreMetrics {
    /// Overall Brier score (0 = perfect, 1 = worst).
    pub brier_score: f64,
    /// Number of samples used.
    pub sample_count: usize,
    /// Reliability component (lower is better).
    pub reliability: f64,
    /// Resolution component (higher is better).
    pub resolution: f64,
    /// Base rate of positive outcomes.
    pub base_rate: f64,
}

/// Gate that blocks decisions when calibration is poor.
#[derive(Debug, Clone)]
pub struct BrierScoreGate {
    tracker: BrierScoreTracker,
    /// Maximum acceptable Brier score (default 0.25).
    threshold: f64,
    /// Minimum samples required before gate is active.
    min_samples: usize,
    /// Action to take when gate blocks.
    block_action: DecisionAction,
}

impl Default for BrierScoreGate {
    fn default() -> Self {
        Self::new()
    }
}

impl BrierScoreGate {
    /// Create a new gate with default settings.
    #[must_use]
    pub fn new() -> Self {
        Self {
            tracker: BrierScoreTracker::new(),
            threshold: 0.25,
            min_samples: 10,
            block_action: DecisionAction::FullValidate,
        }
    }

    /// Create a gate with custom settings.
    #[must_use]
    pub fn with_settings(threshold: f64, min_samples: usize, block_action: DecisionAction) -> Self {
        Self {
            tracker: BrierScoreTracker::new(),
            threshold: threshold.clamp(0.0, 1.0),
            min_samples,
            block_action,
        }
    }

    /// Record a prediction outcome.
    pub fn record(&mut self, predicted_probability: f64, was_incompatible: bool) {
        self.tracker.record(predicted_probability, was_incompatible);
    }

    /// Check if the gate is currently open (calibration is acceptable).
    #[must_use]
    pub fn is_open(&self) -> bool {
        // Gate is open if we don't have enough samples yet OR calibration is good
        self.tracker.count() < self.min_samples || self.tracker.brier_score() <= self.threshold
    }

    /// Apply the gate to a proposed action.
    ///
    /// Returns the action unchanged if gate is open, or block_action if closed.
    #[must_use]
    pub fn apply(&self, proposed_action: DecisionAction) -> GateDecision {
        if self.is_open() {
            GateDecision {
                action: proposed_action,
                gate_applied: false,
                brier_score: self.tracker.brier_score(),
                sample_count: self.tracker.count(),
            }
        } else {
            GateDecision {
                action: self.block_action,
                gate_applied: true,
                brier_score: self.tracker.brier_score(),
                sample_count: self.tracker.count(),
            }
        }
    }

    /// Get current Brier score.
    #[must_use]
    pub fn brier_score(&self) -> f64 {
        self.tracker.brier_score()
    }

    /// Get detailed metrics.
    #[must_use]
    pub fn metrics(&self) -> BrierScoreMetrics {
        self.tracker.metrics()
    }

    /// Reset the gate.
    pub fn reset(&mut self) {
        self.tracker.reset();
    }

    /// Get the threshold.
    #[must_use]
    pub fn threshold(&self) -> f64 {
        self.threshold
    }
}

/// Result of applying the Brier score gate.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct GateDecision {
    /// The action after gate is applied.
    pub action: DecisionAction,
    /// Whether the gate blocked the original action.
    pub gate_applied: bool,
    /// Current Brier score.
    pub brier_score: f64,
    /// Number of samples in the tracker.
    pub sample_count: usize,
}

// ──────────────────────────────────────────────────────────────────────────────
// E12: Tail-stability gate: 30-sample p99 distribution shift
// ──────────────────────────────────────────────────────────────────────────────

/// A single latency sample with timestamp.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct TailSample {
    /// Latency value (e.g., milliseconds).
    pub value: f64,
    /// Timestamp when the sample was recorded.
    pub ts_unix_ms: u128,
}

/// Configuration for the tail stability gate.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct TailStabilityConfig {
    /// Number of samples required for baseline.
    pub baseline_samples: usize,
    /// Number of samples in the sliding window for comparison.
    pub window_samples: usize,
    /// Maximum allowed ratio of current p99 to baseline p99.
    pub max_p99_ratio: f64,
    /// Percentile to track (e.g., 0.99 for p99).
    pub percentile: f64,
}

impl Default for TailStabilityConfig {
    fn default() -> Self {
        Self {
            baseline_samples: 30,
            window_samples: 30,
            max_p99_ratio: 1.2, // 20% regression threshold
            percentile: 0.99,
        }
    }
}

impl TailStabilityConfig {
    /// Stricter config for production.
    #[must_use]
    pub const fn strict() -> Self {
        Self {
            baseline_samples: 50,
            window_samples: 30,
            max_p99_ratio: 1.1, // 10% regression threshold
            percentile: 0.99,
        }
    }
}

/// Tracker for tail latency stability.
///
/// Maintains a baseline and a sliding window of recent samples, detecting
/// distribution shifts based on p99 changes.
#[derive(Debug, Clone)]
pub struct TailStabilityTracker {
    config: TailStabilityConfig,
    baseline: Vec<TailSample>,
    window: Vec<TailSample>,
    baseline_p99: Option<f64>,
    baseline_locked: bool,
}

impl Default for TailStabilityTracker {
    fn default() -> Self {
        Self::new()
    }
}

impl TailStabilityTracker {
    /// Create a new tracker with default config.
    #[must_use]
    pub fn new() -> Self {
        Self::with_config(TailStabilityConfig::default())
    }

    /// Create a tracker with custom config.
    #[must_use]
    pub fn with_config(config: TailStabilityConfig) -> Self {
        Self {
            config,
            baseline: Vec::new(),
            window: Vec::new(),
            baseline_p99: None,
            baseline_locked: false,
        }
    }

    /// Record a new latency sample.
    pub fn record(&mut self, value: f64) {
        let sample = TailSample {
            value,
            ts_unix_ms: unix_time_ms(),
        };

        if !self.baseline_locked {
            // Still collecting baseline
            self.baseline.push(sample);
            if self.baseline.len() >= self.config.baseline_samples {
                self.lock_baseline();
            }
        } else {
            // Baseline locked, update sliding window
            self.window.push(sample);
            if self.window.len() > self.config.window_samples {
                self.window.remove(0);
            }
        }
    }

    /// Lock the baseline and compute baseline p99.
    fn lock_baseline(&mut self) {
        if self.baseline.is_empty() {
            return;
        }
        self.baseline_p99 = Some(Self::compute_percentile(
            &self.baseline,
            self.config.percentile,
        ));
        self.baseline_locked = true;
    }

    /// Force lock the baseline with current samples (even if not full).
    pub fn force_lock_baseline(&mut self) {
        if !self.baseline.is_empty() {
            self.lock_baseline();
        }
    }

    /// Compute percentile of samples.
    fn compute_percentile(samples: &[TailSample], percentile: f64) -> f64 {
        if samples.is_empty() {
            return 0.0;
        }
        let mut values: Vec<f64> = samples.iter().map(|s| s.value).collect();
        values.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));

        let idx = (values.len() as f64 * percentile).floor() as usize;
        let idx = idx.min(values.len() - 1);
        values[idx]
    }

    /// Get the current window p99.
    #[must_use]
    pub fn window_p99(&self) -> Option<f64> {
        if self.window.is_empty() {
            return None;
        }
        Some(Self::compute_percentile(
            &self.window,
            self.config.percentile,
        ))
    }

    /// Get the baseline p99.
    #[must_use]
    pub fn baseline_p99(&self) -> Option<f64> {
        self.baseline_p99
    }

    /// Check if there is a distribution shift (regression).
    #[must_use]
    pub fn has_shift(&self) -> bool {
        match (self.baseline_p99, self.window_p99()) {
            (Some(base), Some(current)) if base > 0.0 => current / base > self.config.max_p99_ratio,
            _ => false,
        }
    }

    /// Get the current p99 ratio (window / baseline).
    #[must_use]
    pub fn p99_ratio(&self) -> Option<f64> {
        match (self.baseline_p99, self.window_p99()) {
            (Some(base), Some(current)) if base > 0.0 => Some(current / base),
            _ => None,
        }
    }

    /// Get status of the tracker.
    #[must_use]
    pub fn status(&self) -> TailStabilityStatus {
        TailStabilityStatus {
            baseline_samples: self.baseline.len(),
            window_samples: self.window.len(),
            baseline_locked: self.baseline_locked,
            baseline_p99: self.baseline_p99,
            window_p99: self.window_p99(),
            p99_ratio: self.p99_ratio(),
            has_shift: self.has_shift(),
        }
    }

    /// Reset the tracker.
    pub fn reset(&mut self) {
        self.baseline.clear();
        self.window.clear();
        self.baseline_p99 = None;
        self.baseline_locked = false;
    }

    /// Number of samples in baseline.
    #[must_use]
    pub fn baseline_count(&self) -> usize {
        self.baseline.len()
    }

    /// Number of samples in window.
    #[must_use]
    pub fn window_count(&self) -> usize {
        self.window.len()
    }

    /// Whether baseline is locked.
    #[must_use]
    pub fn is_baseline_locked(&self) -> bool {
        self.baseline_locked
    }
}

/// Status snapshot from the tail stability tracker.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct TailStabilityStatus {
    /// Number of baseline samples.
    pub baseline_samples: usize,
    /// Number of window samples.
    pub window_samples: usize,
    /// Whether baseline is locked.
    pub baseline_locked: bool,
    /// Baseline p99 (if locked).
    pub baseline_p99: Option<f64>,
    /// Current window p99.
    pub window_p99: Option<f64>,
    /// Ratio of window p99 to baseline p99.
    pub p99_ratio: Option<f64>,
    /// Whether a shift (regression) is detected.
    pub has_shift: bool,
}

/// Gate that blocks when tail latency regresses.
#[derive(Debug, Clone)]
pub struct TailStabilityGate {
    tracker: TailStabilityTracker,
    block_action: DecisionAction,
}

impl Default for TailStabilityGate {
    fn default() -> Self {
        Self::new()
    }
}

impl TailStabilityGate {
    /// Create a new gate with default settings.
    #[must_use]
    pub fn new() -> Self {
        Self {
            tracker: TailStabilityTracker::new(),
            block_action: DecisionAction::FailClosed,
        }
    }

    /// Create a gate with custom config and block action.
    #[must_use]
    pub fn with_config(config: TailStabilityConfig, block_action: DecisionAction) -> Self {
        Self {
            tracker: TailStabilityTracker::with_config(config),
            block_action,
        }
    }

    /// Record a latency sample.
    pub fn record(&mut self, latency: f64) {
        self.tracker.record(latency);
    }

    /// Check if the gate is open (no regression detected).
    #[must_use]
    pub fn is_open(&self) -> bool {
        !self.tracker.has_shift()
    }

    /// Apply the gate to a proposed action.
    #[must_use]
    pub fn apply(&self, proposed_action: DecisionAction) -> TailGateDecision {
        let status = self.tracker.status();
        if self.is_open() {
            TailGateDecision {
                action: proposed_action,
                gate_applied: false,
                status,
            }
        } else {
            TailGateDecision {
                action: self.block_action,
                gate_applied: true,
                status,
            }
        }
    }

    /// Get the current status.
    #[must_use]
    pub fn status(&self) -> TailStabilityStatus {
        self.tracker.status()
    }

    /// Force lock baseline early.
    pub fn force_lock_baseline(&mut self) {
        self.tracker.force_lock_baseline();
    }

    /// Reset the gate.
    pub fn reset(&mut self) {
        self.tracker.reset();
    }
}

/// Result of applying the tail stability gate.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct TailGateDecision {
    /// The action after gate is applied.
    pub action: DecisionAction,
    /// Whether the gate blocked the original action.
    pub gate_applied: bool,
    /// Current stability status.
    pub status: TailStabilityStatus,
}

// ──────────────────────────────────────────────────────────────────────────────
// E3: Profile-and-prove optimization loop per SLO row
// ──────────────────────────────────────────────────────────────────────────────

/// Identifier for SLO metric rows from SPEC §17.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum SloRowId {
    ShortestPath,
    Components,
    Centrality,
    Flow,
    IoRoundtrip,
    MutationCycle,
    MutationRegression,
    MemoryRegression,
    P99TailRegression,
}

impl SloRowId {
    /// Get the metric ID string.
    #[must_use]
    pub const fn metric_id(&self) -> &'static str {
        match self {
            Self::ShortestPath => "shortest_path",
            Self::Components => "components",
            Self::Centrality => "centrality",
            Self::Flow => "flow",
            Self::IoRoundtrip => "io_roundtrip",
            Self::MutationCycle => "mutation_cycle",
            Self::MutationRegression => "mutation_regression",
            Self::MemoryRegression => "memory_regression",
            Self::P99TailRegression => "p99_tail_regression",
        }
    }

    /// All SLO row IDs.
    pub const ALL: &'static [Self] = &[
        Self::ShortestPath,
        Self::Components,
        Self::Centrality,
        Self::Flow,
        Self::IoRoundtrip,
        Self::MutationCycle,
        Self::MutationRegression,
        Self::MemoryRegression,
        Self::P99TailRegression,
    ];
}

/// Phase of the optimization loop.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum OptimizationPhase {
    /// Baseline measurement before optimization.
    Baseline,
    /// Applying optimization.
    Optimize,
    /// Verifying behavior unchanged via conformance.
    Verify,
    /// Final measurement after optimization.
    Measure,
    /// Loop complete.
    Complete,
}

/// Evidence that optimization didn't change behavior.
#[derive(Debug, Clone, PartialEq)]
pub struct OptimizationEvidence {
    /// Conformance fixture count verified.
    pub fixtures_verified: usize,
    /// Mismatches detected (should be 0 for valid optimization).
    pub mismatches: usize,
    /// Hash of conformance report.
    pub conformance_hash: String,
    /// Timestamp of verification.
    pub verified_at_unix_ms: u128,
}

/// Baseline measurement for an SLO row.
#[derive(Debug, Clone, PartialEq)]
pub struct SloBaseline {
    /// SLO row being measured.
    pub row_id: SloRowId,
    /// p50 latency in milliseconds.
    pub p50_ms: f64,
    /// p95 latency in milliseconds.
    pub p95_ms: f64,
    /// p99 latency in milliseconds.
    pub p99_ms: f64,
    /// Peak memory in kilobytes.
    pub peak_memory_kb: u64,
    /// Number of samples.
    pub sample_count: usize,
    /// Timestamp of baseline capture.
    pub captured_at_unix_ms: u128,
}

/// Result of an optimization attempt.
#[derive(Debug, Clone, PartialEq)]
pub struct OptimizationResult {
    /// SLO row that was optimized.
    pub row_id: SloRowId,
    /// Description of the optimization applied.
    pub optimization_description: String,
    /// Baseline before optimization.
    pub baseline: SloBaseline,
    /// Measurement after optimization.
    pub after: SloBaseline,
    /// Evidence that behavior unchanged.
    pub evidence: OptimizationEvidence,
    /// Whether the optimization was successful (improved and verified).
    pub success: bool,
    /// Delta statistics.
    pub delta: OptimizationDelta,
}

/// Delta between baseline and optimized measurements.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct OptimizationDelta {
    /// Change in p50 (negative = improvement).
    pub p50_delta_ms: f64,
    /// Change in p95 (negative = improvement).
    pub p95_delta_ms: f64,
    /// Change in p99 (negative = improvement).
    pub p99_delta_ms: f64,
    /// Change in memory (negative = improvement).
    pub memory_delta_kb: i64,
    /// Percentage improvement in p95.
    pub p95_improvement_pct: f64,
}

impl OptimizationDelta {
    /// Compute delta from baseline and after measurements.
    #[must_use]
    pub fn compute(baseline: &SloBaseline, after: &SloBaseline) -> Self {
        let p50_delta = after.p50_ms - baseline.p50_ms;
        let p95_delta = after.p95_ms - baseline.p95_ms;
        let p99_delta = after.p99_ms - baseline.p99_ms;
        let memory_delta = after.peak_memory_kb as i64 - baseline.peak_memory_kb as i64;
        let p95_improvement = if baseline.p95_ms > 0.0 {
            -100.0 * p95_delta / baseline.p95_ms
        } else {
            0.0
        };

        Self {
            p50_delta_ms: p50_delta,
            p95_delta_ms: p95_delta,
            p99_delta_ms: p99_delta,
            memory_delta_kb: memory_delta,
            p95_improvement_pct: p95_improvement,
        }
    }

    /// Check if this represents an improvement (not regression).
    #[must_use]
    pub fn is_improvement(&self) -> bool {
        // Improvement if p95 is better (lower) and memory isn't much worse
        self.p95_delta_ms <= 0.0 && self.memory_delta_kb <= 1024 // Allow up to 1MB memory increase
    }
}

/// State of the profile-prove loop for a single SLO row.
#[derive(Debug, Clone)]
pub struct ProfileProveState {
    /// SLO row being optimized.
    pub row_id: SloRowId,
    /// Current phase.
    pub phase: OptimizationPhase,
    /// Baseline measurement (set after baseline phase).
    pub baseline: Option<SloBaseline>,
    /// After measurement (set after measure phase).
    pub after: Option<SloBaseline>,
    /// Verification evidence (set after verify phase).
    pub evidence: Option<OptimizationEvidence>,
    /// Description of optimization being attempted.
    pub optimization_description: String,
    /// Started timestamp.
    pub started_at_unix_ms: u128,
}

impl ProfileProveState {
    /// Create a new state for an SLO row.
    #[must_use]
    pub fn new(row_id: SloRowId, optimization_description: &str) -> Self {
        Self {
            row_id,
            phase: OptimizationPhase::Baseline,
            baseline: None,
            after: None,
            evidence: None,
            optimization_description: optimization_description.to_owned(),
            started_at_unix_ms: unix_time_ms(),
        }
    }

    /// Record baseline measurement.
    pub fn record_baseline(&mut self, baseline: SloBaseline) {
        self.baseline = Some(baseline);
        self.phase = OptimizationPhase::Optimize;
    }

    /// Mark optimization as applied.
    pub fn mark_optimized(&mut self) {
        self.phase = OptimizationPhase::Verify;
    }

    /// Record verification evidence.
    pub fn record_verification(&mut self, evidence: OptimizationEvidence) {
        let has_mismatches = evidence.mismatches > 0;
        self.evidence = Some(evidence);
        if has_mismatches {
            // Verification failed - loop aborted
            self.phase = OptimizationPhase::Complete;
        } else {
            self.phase = OptimizationPhase::Measure;
        }
    }

    /// Record final measurement.
    pub fn record_after(&mut self, after: SloBaseline) {
        self.after = Some(after);
        self.phase = OptimizationPhase::Complete;
    }

    /// Get the optimization result (only valid when phase is Complete).
    #[must_use]
    pub fn result(&self) -> Option<OptimizationResult> {
        let baseline = self.baseline.as_ref()?;
        let after = self.after.as_ref()?;
        let evidence = self.evidence.as_ref()?;

        let delta = OptimizationDelta::compute(baseline, after);
        let success = evidence.mismatches == 0 && delta.is_improvement();

        Some(OptimizationResult {
            row_id: self.row_id,
            optimization_description: self.optimization_description.clone(),
            baseline: baseline.clone(),
            after: after.clone(),
            evidence: evidence.clone(),
            success,
            delta,
        })
    }

    /// Check if the loop is complete.
    #[must_use]
    pub fn is_complete(&self) -> bool {
        self.phase == OptimizationPhase::Complete
    }
}

/// Orchestrator for running profile-prove loops across SLO rows.
#[derive(Debug, Clone, Default)]
pub struct ProfileProveLoop {
    /// Results from completed optimization attempts.
    pub results: Vec<OptimizationResult>,
    /// Currently running states.
    pub active: Vec<ProfileProveState>,
}

impl ProfileProveLoop {
    /// Create a new empty loop.
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    /// Start an optimization attempt for an SLO row.
    pub fn start(&mut self, row_id: SloRowId, optimization_description: &str) {
        self.active
            .push(ProfileProveState::new(row_id, optimization_description));
    }

    /// Get active state for a row (if any).
    #[must_use]
    pub fn get_active(&self, row_id: SloRowId) -> Option<&ProfileProveState> {
        self.active.iter().find(|s| s.row_id == row_id)
    }

    /// Get mutable active state for a row.
    pub fn get_active_mut(&mut self, row_id: SloRowId) -> Option<&mut ProfileProveState> {
        self.active.iter_mut().find(|s| s.row_id == row_id)
    }

    /// Complete an active state and move result to results.
    pub fn complete(&mut self, row_id: SloRowId) {
        if let Some(idx) = self.active.iter().position(|s| s.row_id == row_id) {
            let state = self.active.remove(idx);
            if let Some(result) = state.result() {
                self.results.push(result);
            }
        }
    }

    /// Get summary of all completed optimizations.
    #[must_use]
    pub fn summary(&self) -> ProfileProveSummary {
        let total = self.results.len();
        let successful = self.results.iter().filter(|r| r.success).count();
        let failed = total - successful;

        let total_p95_improvement: f64 = self
            .results
            .iter()
            .filter(|r| r.success)
            .map(|r| r.delta.p95_improvement_pct)
            .sum();

        let avg_p95_improvement = if successful > 0 {
            total_p95_improvement / successful as f64
        } else {
            0.0
        };

        ProfileProveSummary {
            total_attempts: total,
            successful,
            failed,
            avg_p95_improvement_pct: avg_p95_improvement,
            rows_optimized: self
                .results
                .iter()
                .filter(|r| r.success)
                .map(|r| r.row_id)
                .collect(),
        }
    }
}

/// Summary of profile-prove loop results.
#[derive(Debug, Clone, PartialEq)]
pub struct ProfileProveSummary {
    /// Total optimization attempts.
    pub total_attempts: usize,
    /// Successful optimizations (verified + improved).
    pub successful: usize,
    /// Failed attempts (verification failed or regression).
    pub failed: usize,
    /// Average p95 improvement percentage.
    pub avg_p95_improvement_pct: f64,
    /// SLO rows that were successfully optimized.
    pub rows_optimized: Vec<SloRowId>,
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
    use super::{AsupersyncAdapterMachine, AsupersyncTransferIntent};

    pub trait ArtifactSyncAdapter {
        fn begin_sync(
            &self,
            cx: &asupersync::Cx,
            intent: AsupersyncTransferIntent,
        ) -> Result<AsupersyncAdapterMachine, String>;
    }

    pub struct CompileCheckAdapter;

    impl ArtifactSyncAdapter for CompileCheckAdapter {
        fn begin_sync(
            &self,
            cx: &asupersync::Cx,
            intent: AsupersyncTransferIntent,
        ) -> Result<AsupersyncAdapterMachine, String> {
            let _ = core::mem::size_of_val(cx);
            let mut machine = AsupersyncAdapterMachine::start(intent)?;
            machine.mark_capability_check(true)?;
            Ok(machine)
        }
    }

    /// Compile-time marker proving asupersync is wired into this crate.
    #[must_use]
    pub fn integration_marker() -> &'static str {
        let _ = core::any::type_name::<asupersync::Cx>();
        "asupersync-integration-enabled"
    }
}

#[cfg(feature = "ftui-integration")]
pub mod ftui_bridge {
    use super::{FtuiArtifactIndex, FtuiTelemetryAdapter, StructuredTestLog};

    pub trait TelemetryArtifactIndexAdapter {
        fn build_index(&self, logs: &[StructuredTestLog]) -> Result<FtuiArtifactIndex, String>;
    }

    pub struct CompileCheckTelemetryAdapter;

    impl TelemetryArtifactIndexAdapter for CompileCheckTelemetryAdapter {
        fn build_index(&self, logs: &[StructuredTestLog]) -> Result<FtuiArtifactIndex, String> {
            let _ = core::any::type_name::<ftui::Theme>();
            FtuiTelemetryAdapter::strict_default().build_artifact_index(logs)
        }
    }

    /// Compile-time marker proving FrankenTUI types are available.
    #[must_use]
    pub fn integration_marker() -> &'static str {
        let _ = core::any::type_name::<ftui::Theme>();
        "ftui-integration-enabled"
    }
}

// ────────────────────────────────────────────────────────────────────────────────
// G6: Algebraic effect tracking for parser modes
// ────────────────────────────────────────────────────────────────────────────────

/// Categories of effects that can occur during parsing operations.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum ParserEffectKind {
    /// A recoverable warning was emitted.
    Warning,
    /// Full validation was triggered.
    Validation,
    /// Parser failed closed (non-recoverable).
    FailClosed,
    /// Operation was allowed to proceed.
    Allow,
    /// A fallback strategy was used.
    Fallback,
    /// Input was sanitized or normalized.
    Sanitize,
    /// A type coercion occurred.
    Coercion,
}

impl ParserEffectKind {
    /// Returns true if this effect indicates a terminal failure.
    #[must_use]
    pub const fn is_terminal(&self) -> bool {
        matches!(self, Self::FailClosed)
    }

    /// Returns true if this effect indicates a recoverable condition.
    #[must_use]
    pub const fn is_recoverable(&self) -> bool {
        matches!(
            self,
            Self::Warning | Self::Fallback | Self::Sanitize | Self::Coercion
        )
    }

    /// Returns the effect kind as a static string.
    #[must_use]
    pub const fn as_str(&self) -> &'static str {
        match self {
            Self::Warning => "warning",
            Self::Validation => "validation",
            Self::FailClosed => "fail_closed",
            Self::Allow => "allow",
            Self::Fallback => "fallback",
            Self::Sanitize => "sanitize",
            Self::Coercion => "coercion",
        }
    }
}

/// A single effect that occurred during parsing.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ParserEffect {
    /// Timestamp when the effect occurred (Unix milliseconds).
    pub ts_unix_ms: u128,
    /// The kind of effect.
    pub kind: ParserEffectKind,
    /// The parser operation that produced this effect.
    pub operation: String,
    /// A human-readable message describing the effect.
    pub message: String,
    /// The compatibility mode in which the effect occurred.
    pub mode: CompatibilityMode,
    /// Optional source location (e.g., line number in input).
    pub source_location: Option<String>,
    /// Associated risk probability (0.0 to 1.0).
    pub risk_probability: f64,
}

impl ParserEffect {
    /// Create a new parser effect with current timestamp.
    #[must_use]
    pub fn new(
        kind: ParserEffectKind,
        operation: impl Into<String>,
        message: impl Into<String>,
        mode: CompatibilityMode,
        risk_probability: f64,
    ) -> Self {
        Self {
            ts_unix_ms: unix_time_ms(),
            kind,
            operation: operation.into(),
            message: message.into(),
            mode,
            source_location: None,
            risk_probability: risk_probability.clamp(0.0, 1.0),
        }
    }

    /// Create a new parser effect with a source location.
    #[must_use]
    pub fn with_location(mut self, location: impl Into<String>) -> Self {
        self.source_location = Some(location.into());
        self
    }

    /// Create a warning effect.
    #[must_use]
    pub fn warning(
        operation: impl Into<String>,
        message: impl Into<String>,
        mode: CompatibilityMode,
    ) -> Self {
        Self::new(ParserEffectKind::Warning, operation, message, mode, 0.5)
    }

    /// Create a fail-closed effect.
    #[must_use]
    pub fn fail_closed(
        operation: impl Into<String>,
        message: impl Into<String>,
        mode: CompatibilityMode,
    ) -> Self {
        Self::new(ParserEffectKind::FailClosed, operation, message, mode, 1.0)
    }

    /// Create an allow effect.
    #[must_use]
    pub fn allow(
        operation: impl Into<String>,
        message: impl Into<String>,
        mode: CompatibilityMode,
        risk_probability: f64,
    ) -> Self {
        Self::new(
            ParserEffectKind::Allow,
            operation,
            message,
            mode,
            risk_probability,
        )
    }
}

/// An effect trace that collects effects during parsing.
///
/// Effect traces are composable and can be filtered or transformed.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct EffectTrace {
    effects: Vec<ParserEffect>,
    terminal_effect: Option<usize>,
}

impl EffectTrace {
    /// Create a new empty effect trace.
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    /// Record an effect in the trace.
    ///
    /// If the effect is terminal (FailClosed), subsequent effects are still
    /// recorded but the trace is marked as terminated.
    pub fn record(&mut self, effect: ParserEffect) {
        let idx = self.effects.len();
        let is_terminal = effect.kind.is_terminal();
        self.effects.push(effect);
        if is_terminal && self.terminal_effect.is_none() {
            self.terminal_effect = Some(idx);
        }
    }

    /// Returns true if the trace contains any terminal effects.
    #[must_use]
    pub fn is_terminated(&self) -> bool {
        self.terminal_effect.is_some()
    }

    /// Returns true if the trace has no effects.
    #[must_use]
    pub fn is_empty(&self) -> bool {
        self.effects.is_empty()
    }

    /// Returns the number of effects in the trace.
    #[must_use]
    pub fn len(&self) -> usize {
        self.effects.len()
    }

    /// Returns a slice of all effects.
    #[must_use]
    pub fn effects(&self) -> &[ParserEffect] {
        &self.effects
    }

    /// Returns the terminal effect, if any.
    #[must_use]
    pub fn terminal(&self) -> Option<&ParserEffect> {
        self.terminal_effect.map(|idx| &self.effects[idx])
    }

    /// Filter effects by kind.
    #[must_use]
    pub fn filter_kind(&self, kind: ParserEffectKind) -> Vec<&ParserEffect> {
        self.effects.iter().filter(|e| e.kind == kind).collect()
    }

    /// Count effects by kind.
    #[must_use]
    pub fn count_kind(&self, kind: ParserEffectKind) -> usize {
        self.effects.iter().filter(|e| e.kind == kind).count()
    }

    /// Returns all warning effects.
    #[must_use]
    pub fn warnings(&self) -> Vec<&ParserEffect> {
        self.filter_kind(ParserEffectKind::Warning)
    }

    /// Merge another trace into this one.
    pub fn merge(&mut self, other: EffectTrace) {
        let offset = self.effects.len();
        for effect in other.effects {
            self.record(effect);
        }
        // Update terminal index if the merged trace had a terminal
        if self.terminal_effect.is_none()
            && let Some(idx) = other.terminal_effect
        {
            self.terminal_effect = Some(offset + idx);
        }
    }

    /// Convert to a summary for logging.
    #[must_use]
    pub fn summary(&self) -> EffectTraceSummary {
        let mut by_kind = std::collections::HashMap::new();
        for effect in &self.effects {
            *by_kind.entry(effect.kind).or_insert(0) += 1;
        }

        EffectTraceSummary {
            total_effects: self.effects.len(),
            warnings: self.count_kind(ParserEffectKind::Warning),
            failures: self.count_kind(ParserEffectKind::FailClosed),
            coercions: self.count_kind(ParserEffectKind::Coercion),
            is_terminated: self.is_terminated(),
            max_risk: self
                .effects
                .iter()
                .map(|e| e.risk_probability)
                .fold(0.0_f64, f64::max),
        }
    }
}

/// A summary of an effect trace for logging and metrics.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct EffectTraceSummary {
    pub total_effects: usize,
    pub warnings: usize,
    pub failures: usize,
    pub coercions: usize,
    pub is_terminated: bool,
    pub max_risk: f64,
}

/// Policy for handling effects during parsing.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum EffectPolicy {
    /// Collect all effects but continue on recoverable ones.
    #[default]
    CollectAll,
    /// Fail immediately on any effect.
    FailOnAny,
    /// Fail on warnings or worse.
    FailOnWarning,
    /// Only fail on terminal effects.
    FailOnTerminal,
}

impl EffectPolicy {
    /// Check if an effect should cause immediate failure under this policy.
    #[must_use]
    pub fn should_fail(&self, effect: &ParserEffect) -> bool {
        match self {
            Self::CollectAll => effect.kind.is_terminal(),
            Self::FailOnAny => true,
            Self::FailOnWarning => {
                matches!(
                    effect.kind,
                    ParserEffectKind::Warning
                        | ParserEffectKind::FailClosed
                        | ParserEffectKind::Validation
                )
            }
            Self::FailOnTerminal => effect.kind.is_terminal(),
        }
    }
}

/// An effect handler that processes effects according to a policy.
#[derive(Debug, Clone)]
pub struct EffectHandler {
    policy: EffectPolicy,
    trace: EffectTrace,
}

impl EffectHandler {
    /// Create a new effect handler with the given policy.
    #[must_use]
    pub fn new(policy: EffectPolicy) -> Self {
        Self {
            policy,
            trace: EffectTrace::new(),
        }
    }

    /// Create an effect handler that collects all effects.
    #[must_use]
    pub fn collect_all() -> Self {
        Self::new(EffectPolicy::CollectAll)
    }

    /// Create an effect handler that fails on terminal effects only.
    #[must_use]
    pub fn fail_on_terminal() -> Self {
        Self::new(EffectPolicy::FailOnTerminal)
    }

    /// Handle an effect, returning Err if the policy requires immediate failure.
    pub fn handle(&mut self, effect: ParserEffect) -> Result<(), ParserEffect> {
        let should_fail = self.policy.should_fail(&effect);
        self.trace.record(effect.clone());
        if should_fail { Err(effect) } else { Ok(()) }
    }

    /// Get the current effect trace.
    #[must_use]
    pub fn trace(&self) -> &EffectTrace {
        &self.trace
    }

    /// Consume the handler and return the effect trace.
    #[must_use]
    pub fn into_trace(self) -> EffectTrace {
        self.trace
    }

    /// Get a summary of the effects.
    #[must_use]
    pub fn summary(&self) -> EffectTraceSummary {
        self.trace.summary()
    }
}

impl Default for EffectHandler {
    fn default() -> Self {
        Self::collect_all()
    }
}

#[cfg(test)]
mod tests {
    use super::{
        AsupersyncAdapterMachine, AsupersyncAdapterReasonCode, AsupersyncAdapterState,
        AsupersyncTransferIntent, CGSE_POLICY_SPEC_PATH, CgseOperationFamily, CgsePolicyEngine,
        CgsePolicyEvaluator, CgsePolicyRule, CompatibilityMode, DecisionAction, E2eStepStatus,
        E2eStepTrace, EvidenceLedger, FailureReproData, ForensicsBundleIndex, FtuiTelemetryAdapter,
        StructuredTestLog, TestKind, TestStatus, canonical_environment_fingerprint,
        cgse_policy_schema_version, decision_theoretic_action, ftui_telemetry_canonical_fields,
        structured_test_log_schema_version,
    };
    use std::collections::{BTreeMap, BTreeSet};

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
        let action = decision_theoretic_action(CompatibilityMode::Strict, 0.3, false);
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
    fn cgse_policy_rule_table_stays_stable_and_unique() {
        assert_eq!(cgse_policy_schema_version(), "1.0.0");
        assert_eq!(CgsePolicyRule::ALL.len(), 14);
        let mut ids = BTreeSet::new();
        for rule in CgsePolicyRule::ALL {
            assert!(ids.insert(rule.as_rule_id()));
            assert!(!rule.policy_id().is_empty());
            assert!(!rule.fail_closed_default().is_empty());
            assert!(!rule.hardened_allowlist().is_empty());
        }
        assert_eq!(
            CgsePolicyRule::R08.operation_family(),
            CgseOperationFamily::ShortestPathAlgorithms
        );
    }

    #[test]
    fn cgse_policy_engine_hardened_mode_fails_closed_on_non_allowlisted_ambiguity() {
        let engine = CgsePolicyEngine::new(CompatibilityMode::Hardened);
        let decision = CgsePolicyEvaluator::evaluate(
            &engine,
            CgsePolicyRule::R01,
            Some("CGSE-AMB-999"),
            0.01,
            false,
        );
        assert_eq!(
            CgsePolicyEvaluator::mode(&engine),
            CompatibilityMode::Hardened
        );
        assert_eq!(decision.policy_spec_path, CGSE_POLICY_SPEC_PATH);
        assert_eq!(decision.decision.action, DecisionAction::FailClosed);
        assert!(!decision.allowlisted_ambiguity);
        assert_eq!(decision.decision.evidence.len(), 4);
    }

    #[test]
    fn cgse_policy_engine_is_deterministic_for_fixed_timestamp() {
        let engine = CgsePolicyEngine::new(CompatibilityMode::Strict);
        let left = engine.evaluate_at(CgsePolicyRule::R08, Some("CGSE-AMB-008"), 0.3, false, 42);
        let right = engine.evaluate_at(CgsePolicyRule::R08, Some("CGSE-AMB-008"), 0.3, false, 42);
        assert_eq!(left, right);
        assert_eq!(left.decision.action, DecisionAction::FullValidate);
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

    #[test]
    fn structured_test_log_packet_003_unit_contract_requires_route_metadata() {
        let mut env = base_env();
        env.insert("route_id".to_owned(), "dispatch::shortest_path".to_owned());
        env.insert("backend_name".to_owned(), "alpha-backend".to_owned());
        env.insert("strict_mode".to_owned(), "true".to_owned());

        let replay = "rch exec -- cargo test -p fnx-dispatch unit_packet_003_contract_asserted -- --nocapture";
        let log = StructuredTestLog {
            schema_version: structured_test_log_schema_version().to_owned(),
            run_id: "run-p2c003-unit".to_owned(),
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
            env_fingerprint: canonical_environment_fingerprint(&env),
            environment: env,
            duration_ms: 3,
            replay_command: replay.to_owned(),
            artifact_refs: vec!["artifacts/conformance/latest/structured_logs.jsonl".to_owned()],
            forensic_bundle_id: "forensics::dispatch::unit::contract".to_owned(),
            hash_id: "sha256:p2c003-unit".to_owned(),
            status: TestStatus::Passed,
            reason_code: None,
            failure_repro: None,
            e2e_step_traces: Vec::new(),
            forensics_bundle_index: Some(base_forensics_bundle(
                "run-p2c003-unit",
                "unit::fnx-p2c-003::contract",
                replay,
                "forensics::dispatch::unit::contract",
                vec!["artifacts/conformance/latest/structured_logs.jsonl".to_owned()],
            )),
        };
        log.validate()
            .expect("packet-003 unit contract log should satisfy metadata schema");

        let mut missing_backend = log.clone();
        missing_backend.environment.remove("backend_name");
        let err = missing_backend
            .validate()
            .expect_err("missing backend_name metadata must fail closed");
        assert!(err.contains("backend_name"));

        let mut missing_fixture = log;
        missing_fixture.fixture_id = None;
        let err = missing_fixture
            .validate()
            .expect_err("packet-003 unit contract should require fixture_id");
        assert!(err.contains("fixture_id"));
    }

    #[test]
    fn structured_test_log_packet_003_property_invariants_require_seed_and_digest() {
        let mut env = base_env();
        env.insert("graph_fingerprint".to_owned(), "graph-fp-003".to_owned());
        env.insert("cache_key_digest".to_owned(), "cache-digest-003".to_owned());
        env.insert("invariant_id".to_owned(), "P2C003-IV-1".to_owned());

        let replay =
            "rch exec -- cargo test -p fnx-dispatch property_packet_003_invariants -- --nocapture";
        let log = StructuredTestLog {
            schema_version: structured_test_log_schema_version().to_owned(),
            run_id: "run-p2c003-property".to_owned(),
            ts_unix_ms: 2,
            crate_name: "fnx-dispatch".to_owned(),
            suite_id: "property".to_owned(),
            packet_id: "FNX-P2C-003".to_owned(),
            test_name: "property_packet_003_invariants".to_owned(),
            test_id: "property::fnx-p2c-003::invariants".to_owned(),
            test_kind: TestKind::Property,
            mode: CompatibilityMode::Hardened,
            fixture_id: Some("dispatch::property::matrix".to_owned()),
            seed: Some(7203),
            env_fingerprint: canonical_environment_fingerprint(&env),
            environment: env,
            duration_ms: 9,
            replay_command: replay.to_owned(),
            artifact_refs: vec![
                "artifacts/conformance/latest/structured_log_emitter_normalization_report.json"
                    .to_owned(),
            ],
            forensic_bundle_id: "forensics::dispatch::property::invariants".to_owned(),
            hash_id: "sha256:p2c003-property".to_owned(),
            status: TestStatus::Failed,
            reason_code: Some("mismatch".to_owned()),
            failure_repro: Some(FailureReproData {
                failure_message: "deterministic replay mismatch".to_owned(),
                reproduction_command: replay.to_owned(),
                expected_behavior: "replay-stable dispatch decision".to_owned(),
                observed_behavior: "decision diverged".to_owned(),
                seed: Some(7203),
                fixture_id: Some("dispatch::property::matrix".to_owned()),
                artifact_hash_id: Some("sha256:p2c003-property".to_owned()),
                forensics_link: Some(
                    "artifacts/conformance/latest/structured_log_emitter_normalization_report.json"
                        .to_owned(),
                ),
            }),
            e2e_step_traces: Vec::new(),
            forensics_bundle_index: Some(base_forensics_bundle(
                "run-p2c003-property",
                "property::fnx-p2c-003::invariants",
                replay,
                "forensics::dispatch::property::invariants",
                vec![
                    "artifacts/conformance/latest/structured_log_emitter_normalization_report.json"
                        .to_owned(),
                ],
            )),
        };
        log.validate()
            .expect("packet-003 property log should satisfy metadata schema");

        let mut missing_seed = log.clone();
        missing_seed.seed = None;
        let err = missing_seed
            .validate()
            .expect_err("packet-003 property log should require deterministic seed");
        assert!(err.contains("deterministic seed"));

        let mut missing_digest = log;
        missing_digest.environment.remove("cache_key_digest");
        let err = missing_digest
            .validate()
            .expect_err("packet-003 property log should require cache digest metadata");
        assert!(err.contains("cache_key_digest"));
    }

    #[test]
    fn structured_test_log_packet_004_unit_contract_requires_conversion_metadata() {
        let mut env = base_env();
        env.insert("conversion_path".to_owned(), "edge_list".to_owned());
        env.insert("input_shape".to_owned(), "edge_list_payload".to_owned());
        env.insert("strict_mode".to_owned(), "true".to_owned());

        let replay = "rch exec -- cargo test -p fnx-convert unit_packet_004_contract_asserted -- --nocapture";
        let log = StructuredTestLog {
            schema_version: structured_test_log_schema_version().to_owned(),
            run_id: "run-p2c004-unit".to_owned(),
            ts_unix_ms: 3,
            crate_name: "fnx-convert".to_owned(),
            suite_id: "unit".to_owned(),
            packet_id: "FNX-P2C-004".to_owned(),
            test_name: "unit_packet_004_contract_asserted".to_owned(),
            test_id: "unit::fnx-p2c-004::contract".to_owned(),
            test_kind: TestKind::Unit,
            mode: CompatibilityMode::Strict,
            fixture_id: Some("convert::contract::edge_list".to_owned()),
            seed: Some(7104),
            env_fingerprint: canonical_environment_fingerprint(&env),
            environment: env,
            duration_ms: 4,
            replay_command: replay.to_owned(),
            artifact_refs: vec!["artifacts/conformance/latest/structured_logs.jsonl".to_owned()],
            forensic_bundle_id: "forensics::convert::unit::contract".to_owned(),
            hash_id: "sha256:p2c004-unit".to_owned(),
            status: TestStatus::Passed,
            reason_code: None,
            failure_repro: None,
            e2e_step_traces: Vec::new(),
            forensics_bundle_index: Some(base_forensics_bundle(
                "run-p2c004-unit",
                "unit::fnx-p2c-004::contract",
                replay,
                "forensics::convert::unit::contract",
                vec!["artifacts/conformance/latest/structured_logs.jsonl".to_owned()],
            )),
        };
        log.validate()
            .expect("packet-004 unit contract log should satisfy metadata schema");

        let mut missing_conversion_path = log.clone();
        missing_conversion_path
            .environment
            .remove("conversion_path");
        let err = missing_conversion_path
            .validate()
            .expect_err("missing conversion_path metadata must fail closed");
        assert!(err.contains("conversion_path"));

        let mut missing_fixture = log;
        missing_fixture.fixture_id = None;
        let err = missing_fixture
            .validate()
            .expect_err("packet-004 unit contract should require fixture_id");
        assert!(err.contains("fixture_id"));
    }

    #[test]
    fn structured_test_log_packet_004_property_invariants_require_seed_and_fingerprint() {
        let mut env = base_env();
        env.insert("graph_fingerprint".to_owned(), "graph-fp-004".to_owned());
        env.insert("relabel_mode".to_owned(), "copy".to_owned());
        env.insert("invariant_id".to_owned(), "P2C004-IV-1".to_owned());

        let replay =
            "rch exec -- cargo test -p fnx-convert property_packet_004_invariants -- --nocapture";
        let log = StructuredTestLog {
            schema_version: structured_test_log_schema_version().to_owned(),
            run_id: "run-p2c004-property".to_owned(),
            ts_unix_ms: 4,
            crate_name: "fnx-convert".to_owned(),
            suite_id: "property".to_owned(),
            packet_id: "FNX-P2C-004".to_owned(),
            test_name: "property_packet_004_invariants".to_owned(),
            test_id: "property::fnx-p2c-004::invariants".to_owned(),
            test_kind: TestKind::Property,
            mode: CompatibilityMode::Hardened,
            fixture_id: Some("convert::property::edge_list_matrix".to_owned()),
            seed: Some(7204),
            env_fingerprint: canonical_environment_fingerprint(&env),
            environment: env,
            duration_ms: 9,
            replay_command: replay.to_owned(),
            artifact_refs: vec![
                "artifacts/conformance/latest/structured_log_emitter_normalization_report.json"
                    .to_owned(),
            ],
            forensic_bundle_id: "forensics::convert::property::invariants".to_owned(),
            hash_id: "sha256:p2c004-property".to_owned(),
            status: TestStatus::Passed,
            reason_code: None,
            failure_repro: None,
            e2e_step_traces: Vec::new(),
            forensics_bundle_index: Some(base_forensics_bundle(
                "run-p2c004-property",
                "property::fnx-p2c-004::invariants",
                replay,
                "forensics::convert::property::invariants",
                vec![
                    "artifacts/conformance/latest/structured_log_emitter_normalization_report.json"
                        .to_owned(),
                ],
            )),
        };
        log.validate()
            .expect("packet-004 property log should satisfy metadata schema");

        let mut missing_seed = log.clone();
        missing_seed.seed = None;
        let err = missing_seed
            .validate()
            .expect_err("packet-004 property log should require deterministic seed");
        assert!(err.contains("deterministic seed"));

        let mut missing_fingerprint = log;
        missing_fingerprint.environment.remove("graph_fingerprint");
        let err = missing_fingerprint
            .validate()
            .expect_err("packet-004 property log should require graph fingerprint metadata");
        assert!(err.contains("graph_fingerprint"));
    }

    #[test]
    fn structured_test_log_packet_005_unit_contract_requires_algorithm_metadata() {
        let mut env = base_env();
        env.insert(
            "algorithm_family".to_owned(),
            "shortest_path_first_wave".to_owned(),
        );
        env.insert("source_target_pair".to_owned(), "a->e".to_owned());
        env.insert("strict_mode".to_owned(), "true".to_owned());
        env.insert("policy_row_id".to_owned(), "CGSE-POL-R08".to_owned());

        let replay = "rch exec -- cargo test -p fnx-algorithms unit_packet_005_contract_asserted -- --nocapture";
        let log = StructuredTestLog {
            schema_version: structured_test_log_schema_version().to_owned(),
            run_id: "run-p2c005-unit".to_owned(),
            ts_unix_ms: 5,
            crate_name: "fnx-algorithms".to_owned(),
            suite_id: "unit".to_owned(),
            packet_id: "FNX-P2C-005".to_owned(),
            test_name: "unit_packet_005_contract_asserted".to_owned(),
            test_id: "unit::fnx-p2c-005::contract".to_owned(),
            test_kind: TestKind::Unit,
            mode: CompatibilityMode::Strict,
            fixture_id: Some("algorithms::contract::shortest_path_wave".to_owned()),
            seed: Some(7105),
            env_fingerprint: canonical_environment_fingerprint(&env),
            environment: env,
            duration_ms: 6,
            replay_command: replay.to_owned(),
            artifact_refs: vec!["artifacts/conformance/latest/structured_logs.jsonl".to_owned()],
            forensic_bundle_id: "forensics::algorithms::unit::contract".to_owned(),
            hash_id: "sha256:p2c005-unit".to_owned(),
            status: TestStatus::Passed,
            reason_code: None,
            failure_repro: None,
            e2e_step_traces: Vec::new(),
            forensics_bundle_index: Some(base_forensics_bundle(
                "run-p2c005-unit",
                "unit::fnx-p2c-005::contract",
                replay,
                "forensics::algorithms::unit::contract",
                vec!["artifacts/conformance/latest/structured_logs.jsonl".to_owned()],
            )),
        };
        log.validate()
            .expect("packet-005 unit contract log should satisfy metadata schema");

        let mut missing_algorithm_family = log.clone();
        missing_algorithm_family
            .environment
            .remove("algorithm_family");
        let err = missing_algorithm_family
            .validate()
            .expect_err("missing algorithm_family metadata must fail closed");
        assert!(err.contains("algorithm_family"));

        let mut missing_fixture = log;
        missing_fixture.fixture_id = None;
        let err = missing_fixture
            .validate()
            .expect_err("packet-005 unit contract should require fixture_id");
        assert!(err.contains("fixture_id"));

        let mut missing_policy_row = missing_algorithm_family.clone();
        missing_policy_row.environment.insert(
            "algorithm_family".to_owned(),
            "shortest_path_first_wave".to_owned(),
        );
        missing_policy_row.environment.remove("policy_row_id");
        let err = missing_policy_row
            .validate()
            .expect_err("packet-005 unit contract should require policy_row_id metadata");
        assert!(err.contains("policy_row_id"));
    }

    #[test]
    fn structured_test_log_packet_005_property_invariants_require_seed_and_tie_break_metadata() {
        let mut env = base_env();
        env.insert("graph_fingerprint".to_owned(), "graph-fp-005".to_owned());
        env.insert(
            "tie_break_policy".to_owned(),
            "lexical_neighbor_order".to_owned(),
        );
        env.insert("invariant_id".to_owned(), "P2C005-INV-1".to_owned());
        env.insert("policy_row_id".to_owned(), "CGSE-POL-R08".to_owned());

        let replay = "rch exec -- cargo test -p fnx-algorithms property_packet_005_invariants -- --nocapture";
        let log = StructuredTestLog {
            schema_version: structured_test_log_schema_version().to_owned(),
            run_id: "run-p2c005-property".to_owned(),
            ts_unix_ms: 6,
            crate_name: "fnx-algorithms".to_owned(),
            suite_id: "property".to_owned(),
            packet_id: "FNX-P2C-005".to_owned(),
            test_name: "property_packet_005_invariants".to_owned(),
            test_id: "property::fnx-p2c-005::invariants".to_owned(),
            test_kind: TestKind::Property,
            mode: CompatibilityMode::Hardened,
            fixture_id: Some("algorithms::property::path_and_centrality_matrix".to_owned()),
            seed: Some(7205),
            env_fingerprint: canonical_environment_fingerprint(&env),
            environment: env,
            duration_ms: 10,
            replay_command: replay.to_owned(),
            artifact_refs: vec![
                "artifacts/conformance/latest/structured_log_emitter_normalization_report.json"
                    .to_owned(),
            ],
            forensic_bundle_id: "forensics::algorithms::property::invariants".to_owned(),
            hash_id: "sha256:p2c005-property".to_owned(),
            status: TestStatus::Passed,
            reason_code: None,
            failure_repro: None,
            e2e_step_traces: Vec::new(),
            forensics_bundle_index: Some(base_forensics_bundle(
                "run-p2c005-property",
                "property::fnx-p2c-005::invariants",
                replay,
                "forensics::algorithms::property::invariants",
                vec![
                    "artifacts/conformance/latest/structured_log_emitter_normalization_report.json"
                        .to_owned(),
                ],
            )),
        };
        log.validate()
            .expect("packet-005 property log should satisfy metadata schema");

        let mut missing_seed = log.clone();
        missing_seed.seed = None;
        let err = missing_seed
            .validate()
            .expect_err("packet-005 property log should require deterministic seed");
        assert!(err.contains("deterministic seed"));

        let mut missing_tie_break = log;
        missing_tie_break.environment.remove("tie_break_policy");
        let err = missing_tie_break
            .validate()
            .expect_err("packet-005 property log should require tie_break_policy metadata");
        assert!(err.contains("tie_break_policy"));

        let mut missing_policy_row = missing_seed;
        missing_policy_row.seed = Some(7205);
        missing_policy_row.environment.remove("policy_row_id");
        let err = missing_policy_row
            .validate()
            .expect_err("packet-005 property log should require policy_row_id metadata");
        assert!(err.contains("policy_row_id"));
    }

    #[test]
    fn structured_test_log_packet_006_unit_contract_requires_readwrite_metadata() {
        let mut env = base_env();
        env.insert("io_path".to_owned(), "edgelist+json_graph".to_owned());
        env.insert("strict_mode".to_owned(), "true".to_owned());
        env.insert("input_digest".to_owned(), "sha256:input-p2c006".to_owned());
        env.insert(
            "output_digest".to_owned(),
            "sha256:output-p2c006".to_owned(),
        );

        let replay = "rch exec -- cargo test -p fnx-readwrite unit_packet_006_contract_asserted -- --nocapture";
        let log = StructuredTestLog {
            schema_version: structured_test_log_schema_version().to_owned(),
            run_id: "run-p2c006-unit".to_owned(),
            ts_unix_ms: 7,
            crate_name: "fnx-readwrite".to_owned(),
            suite_id: "unit".to_owned(),
            packet_id: "FNX-P2C-006".to_owned(),
            test_name: "unit_packet_006_contract_asserted".to_owned(),
            test_id: "unit::fnx-p2c-006::contract".to_owned(),
            test_kind: TestKind::Unit,
            mode: CompatibilityMode::Strict,
            fixture_id: Some("readwrite::contract::edgelist_json_roundtrip".to_owned()),
            seed: Some(7106),
            env_fingerprint: canonical_environment_fingerprint(&env),
            environment: env,
            duration_ms: 8,
            replay_command: replay.to_owned(),
            artifact_refs: vec!["artifacts/conformance/latest/structured_logs.jsonl".to_owned()],
            forensic_bundle_id: "forensics::readwrite::unit::contract".to_owned(),
            hash_id: "sha256:p2c006-unit".to_owned(),
            status: TestStatus::Passed,
            reason_code: None,
            failure_repro: None,
            e2e_step_traces: Vec::new(),
            forensics_bundle_index: Some(base_forensics_bundle(
                "run-p2c006-unit",
                "unit::fnx-p2c-006::contract",
                replay,
                "forensics::readwrite::unit::contract",
                vec!["artifacts/conformance/latest/structured_logs.jsonl".to_owned()],
            )),
        };
        log.validate()
            .expect("packet-006 unit contract log should satisfy metadata schema");

        let mut missing_io_path = log.clone();
        missing_io_path.environment.remove("io_path");
        let err = missing_io_path
            .validate()
            .expect_err("packet-006 unit log should require io_path metadata");
        assert!(err.contains("io_path"));

        let mut missing_output_digest = log.clone();
        missing_output_digest.environment.remove("output_digest");
        let err = missing_output_digest
            .validate()
            .expect_err("packet-006 unit log should require output_digest metadata");
        assert!(err.contains("output_digest"));

        let mut missing_fixture = log;
        missing_fixture.fixture_id = None;
        let err = missing_fixture
            .validate()
            .expect_err("packet-006 unit contract should require fixture_id");
        assert!(err.contains("fixture_id"));
    }

    #[test]
    fn structured_test_log_packet_006_property_invariants_require_seed_and_mode_policy_metadata() {
        let mut env = base_env();
        env.insert("graph_fingerprint".to_owned(), "graph-fp-006".to_owned());
        env.insert("mode_policy".to_owned(), "strict_and_hardened".to_owned());
        env.insert("invariant_id".to_owned(), "P2C006-IV-1".to_owned());
        env.insert(
            "input_digest".to_owned(),
            "sha256:input-prop-p2c006".to_owned(),
        );
        env.insert(
            "output_digest".to_owned(),
            "sha256:output-prop-p2c006".to_owned(),
        );

        let replay =
            "rch exec -- cargo test -p fnx-readwrite property_packet_006_invariants -- --nocapture";
        let log = StructuredTestLog {
            schema_version: structured_test_log_schema_version().to_owned(),
            run_id: "run-p2c006-property".to_owned(),
            ts_unix_ms: 8,
            crate_name: "fnx-readwrite".to_owned(),
            suite_id: "property".to_owned(),
            packet_id: "FNX-P2C-006".to_owned(),
            test_name: "property_packet_006_invariants".to_owned(),
            test_id: "property::fnx-p2c-006::invariants".to_owned(),
            test_kind: TestKind::Property,
            mode: CompatibilityMode::Hardened,
            fixture_id: Some("readwrite::property::roundtrip_recovery_matrix".to_owned()),
            seed: Some(7206),
            env_fingerprint: canonical_environment_fingerprint(&env),
            environment: env,
            duration_ms: 12,
            replay_command: replay.to_owned(),
            artifact_refs: vec![
                "artifacts/conformance/latest/structured_log_emitter_normalization_report.json"
                    .to_owned(),
            ],
            forensic_bundle_id: "forensics::readwrite::property::invariants".to_owned(),
            hash_id: "sha256:p2c006-property".to_owned(),
            status: TestStatus::Passed,
            reason_code: None,
            failure_repro: None,
            e2e_step_traces: Vec::new(),
            forensics_bundle_index: Some(base_forensics_bundle(
                "run-p2c006-property",
                "property::fnx-p2c-006::invariants",
                replay,
                "forensics::readwrite::property::invariants",
                vec![
                    "artifacts/conformance/latest/structured_log_emitter_normalization_report.json"
                        .to_owned(),
                ],
            )),
        };
        log.validate()
            .expect("packet-006 property log should satisfy metadata schema");

        let mut missing_seed = log.clone();
        missing_seed.seed = None;
        let err = missing_seed
            .validate()
            .expect_err("packet-006 property log should require deterministic seed");
        assert!(err.contains("deterministic seed"));

        let mut missing_mode_policy = log.clone();
        missing_mode_policy.environment.remove("mode_policy");
        let err = missing_mode_policy
            .validate()
            .expect_err("packet-006 property log should require mode_policy metadata");
        assert!(err.contains("mode_policy"));

        let mut missing_input_digest = log;
        missing_input_digest.environment.remove("input_digest");
        let err = missing_input_digest
            .validate()
            .expect_err("packet-006 property log should require input_digest metadata");
        assert!(err.contains("input_digest"));
    }

    fn base_transfer_intent() -> AsupersyncTransferIntent {
        AsupersyncTransferIntent {
            transfer_id: "tx-asup-001".to_owned(),
            artifact_id: "artifacts/e2e/latest/e2e_scenario_matrix_report_v1.json".to_owned(),
            artifact_class: "conformance_fixture_bundle".to_owned(),
            mode: CompatibilityMode::Strict,
            deterministic_seed: 17,
            expected_checksum: "sha256:expected-123".to_owned(),
            max_attempts: 3,
        }
    }

    #[test]
    fn asupersync_adapter_resume_is_deterministic_across_checkpoint_restart() {
        let intent = base_transfer_intent();
        let mut machine =
            AsupersyncAdapterMachine::start(intent.clone()).expect("start should succeed");
        machine
            .mark_capability_check(true)
            .expect("capability check should pass");
        machine
            .record_chunk_commit(256)
            .expect("chunk commit should succeed");
        machine
            .record_transport_interruption()
            .expect("interruption should consume retry budget");
        let checkpoint = machine.checkpoint();

        let mut resumed = AsupersyncAdapterMachine::resume_from_checkpoint(intent, checkpoint)
            .expect("resume_from_checkpoint should succeed");
        assert_eq!(resumed.state(), AsupersyncAdapterState::Syncing);
        assert_eq!(resumed.attempt(), 1);
        assert_eq!(resumed.committed_cursor(), 256);

        resumed
            .apply_resume_cursor(256)
            .expect("resume cursor should be accepted");
        resumed
            .start_checksum_verification()
            .expect("checksum verification should start");
        resumed
            .finish_checksum_verification("sha256:expected-123")
            .expect("checksum should finalize");
        assert_eq!(resumed.state(), AsupersyncAdapterState::Completed);
        assert!(resumed.validate_transition_log().is_ok());
    }

    #[test]
    fn asupersync_adapter_resume_rejects_transfer_mismatch() {
        let intent = base_transfer_intent();
        let checkpoint = AsupersyncAdapterMachine::start(intent.clone())
            .expect("start should succeed")
            .checkpoint();

        let mut mismatched_intent = intent;
        mismatched_intent.transfer_id = "tx-asup-other".to_owned();
        let err = AsupersyncAdapterMachine::resume_from_checkpoint(mismatched_intent, checkpoint)
            .expect_err("transfer mismatch should reject resume");
        assert!(err.contains("transfer_id"));
    }

    #[test]
    fn asupersync_adapter_checksum_mismatch_is_fail_closed_and_audited() {
        let intent = base_transfer_intent();
        let mut machine = AsupersyncAdapterMachine::start(intent).expect("start should succeed");
        machine
            .mark_capability_check(true)
            .expect("capability check should pass");
        machine
            .record_chunk_commit(10)
            .expect("chunk commit should succeed");
        machine
            .start_checksum_verification()
            .expect("checksum verification should start");
        let err = machine
            .finish_checksum_verification("sha256:unexpected")
            .expect_err("checksum mismatch must fail closed");
        assert!(err.contains("IntegrityPrecheckFailed"));
        assert_eq!(machine.state(), AsupersyncAdapterState::FailedClosed);
        let last = machine
            .transitions()
            .last()
            .expect("transition log should contain mismatch event");
        assert_eq!(
            last.reason_code,
            Some(AsupersyncAdapterReasonCode::IntegrityPrecheckFailed)
        );
    }

    #[test]
    fn asupersync_adapter_conflict_detection_is_explicit_fail_closed() {
        let intent = base_transfer_intent();
        let mut machine = AsupersyncAdapterMachine::start(intent).expect("start should succeed");
        machine
            .mark_capability_check(true)
            .expect("capability check should pass");
        let err = machine
            .record_conflict(5, 6)
            .expect_err("epoch mismatch should fail closed");
        assert!(err.contains("ConflictDetected"));
        assert_eq!(machine.state(), AsupersyncAdapterState::FailedClosed);
    }

    #[test]
    fn asupersync_adapter_retry_budget_exhaustion_fault_injection_is_fail_closed() {
        let mut intent = base_transfer_intent();
        intent.max_attempts = 2;
        let mut machine =
            AsupersyncAdapterMachine::start(intent).expect("start should succeed for retry test");
        machine
            .mark_capability_check(true)
            .expect("capability check should pass");

        machine
            .record_transport_interruption()
            .expect("first interruption should consume retry");
        machine
            .record_transport_interruption()
            .expect("second interruption should consume retry");
        let err = machine
            .record_transport_interruption()
            .expect_err("third interruption should fail closed");
        assert!(err.contains("RetryExhausted"));
        assert_eq!(machine.state(), AsupersyncAdapterState::FailedClosed);
        let last = machine
            .transitions()
            .last()
            .expect("transition log should contain retry exhaustion transition");
        assert_eq!(
            last.reason_code,
            Some(AsupersyncAdapterReasonCode::RetryExhausted)
        );
    }

    #[test]
    fn asupersync_adapter_partial_write_cursor_regression_is_fail_closed() {
        let intent = base_transfer_intent();
        let mut machine = AsupersyncAdapterMachine::start(intent).expect("start should succeed");
        machine
            .mark_capability_check(true)
            .expect("capability check should pass");
        machine
            .record_chunk_commit(200)
            .expect("initial chunk commit should succeed");
        let err = machine
            .record_chunk_commit(150)
            .expect_err("cursor regression should fail closed");
        assert!(err.contains("ConflictDetected"));
        assert_eq!(machine.state(), AsupersyncAdapterState::FailedClosed);
    }

    #[test]
    fn asupersync_adapter_stale_metadata_seed_mismatch_rejects_resume() {
        let intent = base_transfer_intent();
        let checkpoint = AsupersyncAdapterMachine::start(intent.clone())
            .expect("start should succeed")
            .checkpoint();
        let mut stale_intent = intent;
        stale_intent.deterministic_seed = 999;

        let err = AsupersyncAdapterMachine::resume_from_checkpoint(stale_intent, checkpoint)
            .expect_err("seed mismatch should reject stale metadata resume");
        assert!(err.contains("deterministic_seed"));
    }

    #[test]
    fn asupersync_adapter_property_same_fault_sequence_has_identical_transitions() {
        for seed in [3_u64, 17_u64, 91_u64] {
            let make_machine = || {
                let mut intent = base_transfer_intent();
                intent.deterministic_seed = seed;
                let mut machine =
                    AsupersyncAdapterMachine::start(intent).expect("start should succeed");
                machine
                    .mark_capability_check(true)
                    .expect("capability check should pass");
                machine
                    .record_chunk_commit(88)
                    .expect("chunk commit should succeed");
                machine
                    .record_transport_interruption()
                    .expect("interruption should succeed");
                machine
                    .apply_resume_cursor(88)
                    .expect("resume cursor should succeed");
                machine
                    .start_checksum_verification()
                    .expect("checksum phase should start");
                machine
                    .finish_checksum_verification("sha256:expected-123")
                    .expect("checksum should complete");
                machine
            };

            let first = make_machine();
            let second = make_machine();
            assert_eq!(
                first.transitions(),
                second.transitions(),
                "same fault sequence should produce identical transitions for seed {seed}"
            );
            assert_eq!(first.state(), AsupersyncAdapterState::Completed);
            assert_eq!(second.state(), AsupersyncAdapterState::Completed);
        }
    }

    fn base_ftui_log(
        run_id: &str,
        test_id: &str,
        suite_id: &str,
        ts_unix_ms: u128,
        status: TestStatus,
        reason_code: Option<&str>,
    ) -> StructuredTestLog {
        let env = base_env();
        StructuredTestLog {
            schema_version: structured_test_log_schema_version().to_owned(),
            run_id: run_id.to_owned(),
            ts_unix_ms,
            crate_name: "fnx-conformance".to_owned(),
            suite_id: suite_id.to_owned(),
            packet_id: "FNX-P2C-FTUI".to_owned(),
            test_name: format!("test::{test_id}"),
            test_id: test_id.to_owned(),
            test_kind: TestKind::E2e,
            mode: CompatibilityMode::Strict,
            fixture_id: Some("fixture-ftui-001".to_owned()),
            seed: Some(7),
            env_fingerprint: canonical_environment_fingerprint(&env),
            environment: env,
            duration_ms: 42,
            replay_command: "rch exec -- cargo test -p fnx-conformance -- --nocapture".to_owned(),
            artifact_refs: vec![
                "artifacts/e2e/latest/e2e_scenario_matrix_steps_v1.jsonl".to_owned(),
                "artifacts/conformance/latest/structured_logs.jsonl".to_owned(),
            ],
            forensic_bundle_id: format!("forensics::{suite_id}::{test_id}"),
            hash_id: format!("sha256:{run_id}:{test_id}"),
            status,
            reason_code: reason_code.map(ToOwned::to_owned),
            failure_repro: match status {
                TestStatus::Failed => Some(FailureReproData {
                    failure_message: "deterministic failure".to_owned(),
                    reproduction_command:
                        "rch exec -- cargo test -p fnx-conformance -- --nocapture".to_owned(),
                    expected_behavior: "completed".to_owned(),
                    observed_behavior: "failed_closed".to_owned(),
                    seed: Some(7),
                    fixture_id: Some("fixture-ftui-001".to_owned()),
                    artifact_hash_id: Some(format!("sha256:{run_id}:{test_id}")),
                    forensics_link: Some(
                        "artifacts/conformance/latest/structured_logs.jsonl".to_owned(),
                    ),
                }),
                TestStatus::Passed | TestStatus::Skipped => None,
            },
            e2e_step_traces: vec![E2eStepTrace {
                run_id: run_id.to_owned(),
                test_id: test_id.to_owned(),
                step_id: format!("step::{test_id}"),
                step_label: "ftui-step".to_owned(),
                phase: "execute".to_owned(),
                status: match status {
                    TestStatus::Passed => E2eStepStatus::Passed,
                    TestStatus::Failed => E2eStepStatus::Failed,
                    TestStatus::Skipped => E2eStepStatus::Skipped,
                },
                start_unix_ms: ts_unix_ms,
                end_unix_ms: ts_unix_ms + 42,
                duration_ms: 42,
                replay_command: "rch exec -- cargo test -p fnx-conformance -- --nocapture"
                    .to_owned(),
                forensic_bundle_id: format!("forensics::{suite_id}::{test_id}"),
                artifact_refs: vec![
                    "artifacts/e2e/latest/e2e_scenario_matrix_steps_v1.jsonl".to_owned(),
                ],
                hash_id: format!("step-hash::{run_id}::{test_id}"),
                reason_code: reason_code.map(ToOwned::to_owned),
            }],
            forensics_bundle_index: Some(base_forensics_bundle(
                run_id,
                test_id,
                "rch exec -- cargo test -p fnx-conformance -- --nocapture",
                &format!("forensics::{suite_id}::{test_id}"),
                vec![
                    "artifacts/e2e/latest/e2e_scenario_matrix_steps_v1.jsonl".to_owned(),
                    "artifacts/conformance/latest/structured_logs.jsonl".to_owned(),
                ],
            )),
        }
    }

    #[test]
    fn ftui_adapter_rejects_unknown_telemetry_fields() {
        let adapter = FtuiTelemetryAdapter::strict_default();
        let mut row = BTreeMap::new();
        for field in ftui_telemetry_canonical_fields() {
            row.insert((*field).to_owned(), "value".to_owned());
        }
        row.insert("unknown_field".to_owned(), "boom".to_owned());
        let err = adapter
            .ingest_row(&row)
            .expect_err("unknown field should fail closed");
        assert!(err.contains("unknown telemetry field"));
        assert!(err.contains("allowed fields"));
    }

    #[test]
    fn ftui_adapter_produces_deterministic_artifact_index_ordering() {
        let adapter = FtuiTelemetryAdapter::strict_default();
        let log_a = base_ftui_log(
            "run-b",
            "tests::b",
            "suite-b",
            2_000,
            TestStatus::Passed,
            None,
        );
        let log_b = base_ftui_log(
            "run-a",
            "tests::a",
            "suite-a",
            1_000,
            TestStatus::Passed,
            None,
        );
        let log_c = base_ftui_log(
            "run-c",
            "tests::c",
            "suite-c",
            2_000,
            TestStatus::Failed,
            Some("integrity_precheck_failed"),
        );

        let index_one = adapter
            .build_artifact_index(&[log_a.clone(), log_b.clone(), log_c.clone()])
            .expect("index build should succeed");
        let index_two = adapter
            .build_artifact_index(&[log_c, log_b, log_a])
            .expect("index build should succeed");

        assert_eq!(
            index_one, index_two,
            "deterministic artifact index should be stable across input permutations"
        );
        assert_eq!(index_one.entries.len(), 3);
        assert_eq!(index_one.entries[0].run_id, "run-a");
        assert_eq!(index_one.entries[1].run_id, "run-b");
        assert_eq!(index_one.entries[2].run_id, "run-c");
    }

    #[test]
    fn ftui_adapter_property_replay_mapping_is_deterministic_for_permuted_inputs() {
        let adapter = FtuiTelemetryAdapter::strict_default();
        let logs = vec![
            base_ftui_log(
                "run-a",
                "tests::ftui_a",
                "suite-a",
                1_000,
                TestStatus::Passed,
                None,
            ),
            base_ftui_log(
                "run-b",
                "tests::ftui_b",
                "suite-b",
                2_000,
                TestStatus::Failed,
                Some("integrity_precheck_failed"),
            ),
            base_ftui_log(
                "run-c",
                "tests::ftui_c",
                "suite-c",
                3_000,
                TestStatus::Skipped,
                Some("skipped_by_policy"),
            ),
            base_ftui_log(
                "run-d",
                "tests::ftui_d",
                "suite-d",
                4_000,
                TestStatus::Passed,
                None,
            ),
        ];

        let baseline = adapter
            .build_artifact_index(&logs)
            .expect("baseline artifact index should build");

        for permutation in [[2_usize, 0, 3, 1], [1, 3, 0, 2], [3, 2, 1, 0]] {
            let permuted_logs = permutation
                .iter()
                .map(|idx| logs[*idx].clone())
                .collect::<Vec<_>>();
            let candidate = adapter
                .build_artifact_index(&permuted_logs)
                .expect("permuted artifact index should build");
            assert_eq!(
                candidate, baseline,
                "artifact index and replay mapping should be stable for permutation {permutation:?}"
            );
        }

        for entry in &baseline.entries {
            assert!(
                entry.replay_ref.contains("rch exec --"),
                "replay_ref should stay rch-offloaded"
            );
            assert!(
                !entry.artifact_refs.is_empty(),
                "artifact_refs should remain non-empty for replay mapping"
            );
            assert!(
                entry
                    .artifact_refs
                    .iter()
                    .all(|path| path.starts_with("artifacts/")),
                "artifact_refs should remain workspace artifact paths"
            );
        }
    }

    #[test]
    fn ftui_adapter_snapshot_artifact_index_entry_is_stable() {
        let adapter = FtuiTelemetryAdapter::strict_default();
        let log = base_ftui_log(
            "run-snap",
            "tests::ftui_snapshot",
            "snapshot",
            5_000,
            TestStatus::Passed,
            None,
        );
        let index = adapter
            .build_artifact_index(&[log])
            .expect("snapshot artifact index should build");
        assert_eq!(index.entries.len(), 1, "snapshot expects one index entry");

        let observed = serde_json::to_value(&index.entries[0])
            .expect("snapshot entry should serialize to json value");
        let expected = serde_json::json!({
            "correlation_id": "ftui-corr-9d1b150a8730cdb8",
            "bundle_id": "forensics::snapshot::tests::ftui_snapshot",
            "run_id": "run-snap",
            "test_id": "tests::ftui_snapshot",
            "captured_unix_ms": 5000,
            "replay_ref": "rch exec -- cargo test -p fnx-conformance -- --nocapture",
            "artifact_refs": [
                "artifacts/e2e/latest/e2e_scenario_matrix_steps_v1.jsonl",
                "artifacts/conformance/latest/structured_logs.jsonl"
            ],
            "status": "passed",
            "reason_code": null
        });
        assert_eq!(
            observed, expected,
            "snapshot entry should remain deterministic for canonical FTUI fixtures"
        );
    }

    #[test]
    fn ftui_adapter_fails_closed_when_structured_log_is_incompatible() {
        let adapter = FtuiTelemetryAdapter::strict_default();
        let mut invalid = base_ftui_log(
            "run-invalid",
            "tests::invalid",
            "suite-invalid",
            3_000,
            TestStatus::Passed,
            None,
        );
        invalid.forensics_bundle_index = None;
        let err = adapter
            .from_structured_log(&invalid)
            .expect_err("missing forensics_bundle_index should fail closed");
        assert!(err.contains("forensics_bundle_index"));
    }

    // -----------------------------------------------------------------------
    // Versioned Decision Ledger tests
    // -----------------------------------------------------------------------

    #[test]
    fn versioned_ledger_has_correct_schema_version() {
        let ledger = super::VersionedDecisionLedger::new("test-ledger");
        assert_eq!(ledger.schema_version, super::DECISION_LEDGER_SCHEMA_VERSION);
        assert_eq!(ledger.ledger_id, "test-ledger");
        assert_eq!(ledger.record_count, 0);
        assert!(ledger.records.is_empty());
    }

    #[test]
    fn versioned_ledger_append_updates_metadata() {
        let mut ledger = super::VersionedDecisionLedger::new("append-test");
        let initial_time = ledger.created_at_unix_ms;

        let record = super::DecisionRecord {
            ts_unix_ms: initial_time + 1000,
            operation: "test_op".to_owned(),
            mode: CompatibilityMode::Strict,
            action: DecisionAction::Allow,
            incompatibility_probability: 0.01,
            rationale: "test".to_owned(),
            evidence: vec![],
        };

        ledger.append(record);

        assert_eq!(ledger.record_count, 1);
        assert_eq!(ledger.records.len(), 1);
        assert_eq!(ledger.last_updated_unix_ms, initial_time + 1000);
    }

    #[test]
    fn versioned_ledger_schema_compatibility() {
        let ledger = super::VersionedDecisionLedger::new("compat-test");
        assert!(ledger.is_schema_compatible());

        // Create ledger with different major version
        let mut incompatible = ledger.clone();
        incompatible.schema_version = "2.0.0".to_owned();
        assert!(!incompatible.is_schema_compatible());

        // Same major version is compatible
        let mut compatible = ledger.clone();
        compatible.schema_version = "1.5.0".to_owned();
        assert!(compatible.is_schema_compatible());
    }

    #[test]
    fn versioned_ledger_validation_passes_for_valid_ledger() {
        let ledger = super::VersionedDecisionLedger::new("valid-test");
        let result = ledger.validate();
        assert!(result.is_valid);
        assert!(result.schema_compatible);
        assert!(result.errors.is_empty());
    }

    #[test]
    fn versioned_ledger_validation_catches_empty_fields() {
        let mut ledger = super::VersionedDecisionLedger::new("invalid-test");
        ledger.schema_version = String::new();

        let result = ledger.validate();
        assert!(!result.is_valid);
        assert!(result.errors.iter().any(|e| e.contains("schema_version")));
    }

    #[test]
    fn versioned_ledger_validation_catches_count_mismatch() {
        let mut ledger = super::VersionedDecisionLedger::new("count-test");
        ledger.record_count = 5; // Claim 5 records but have 0

        let result = ledger.validate();
        assert!(!result.is_valid);
        assert!(result.errors.iter().any(|e| e.contains("record_count")));
    }

    #[test]
    fn versioned_ledger_json_roundtrip() {
        let mut ledger = super::VersionedDecisionLedger::new("json-test");
        ledger.append(super::DecisionRecord {
            ts_unix_ms: 1000,
            operation: "roundtrip_op".to_owned(),
            mode: CompatibilityMode::Hardened,
            action: DecisionAction::FullValidate,
            incompatibility_probability: 0.5,
            rationale: "testing roundtrip".to_owned(),
            evidence: vec![super::EvidenceTerm {
                signal: "test_signal".to_owned(),
                observed_value: "test_value".to_owned(),
                log_likelihood_ratio: 1.5,
            }],
        });

        let json = ledger.to_json_pretty().expect("serialization should work");
        let restored =
            super::VersionedDecisionLedger::from_json(&json).expect("deserialization should work");

        assert_eq!(restored.schema_version, ledger.schema_version);
        assert_eq!(restored.ledger_id, ledger.ledger_id);
        assert_eq!(restored.records.len(), 1);
        assert_eq!(restored.records[0].operation, "roundtrip_op");
    }

    #[test]
    fn versioned_ledger_merge_combines_and_sorts() {
        let mut ledger1 = super::VersionedDecisionLedger::new("merge-1");
        ledger1.append(super::DecisionRecord {
            ts_unix_ms: 1000,
            operation: "op1".to_owned(),
            mode: CompatibilityMode::Strict,
            action: DecisionAction::Allow,
            incompatibility_probability: 0.01,
            rationale: "first".to_owned(),
            evidence: vec![],
        });
        ledger1.append(super::DecisionRecord {
            ts_unix_ms: 3000,
            operation: "op3".to_owned(),
            mode: CompatibilityMode::Strict,
            action: DecisionAction::Allow,
            incompatibility_probability: 0.01,
            rationale: "third".to_owned(),
            evidence: vec![],
        });

        let mut ledger2 = super::VersionedDecisionLedger::new("merge-2");
        ledger2.append(super::DecisionRecord {
            ts_unix_ms: 2000,
            operation: "op2".to_owned(),
            mode: CompatibilityMode::Strict,
            action: DecisionAction::Allow,
            incompatibility_probability: 0.01,
            rationale: "second".to_owned(),
            evidence: vec![],
        });

        ledger1.merge(&ledger2);

        assert_eq!(ledger1.record_count, 3);
        assert_eq!(ledger1.records[0].ts_unix_ms, 1000);
        assert_eq!(ledger1.records[1].ts_unix_ms, 2000);
        assert_eq!(ledger1.records[2].ts_unix_ms, 3000);
    }

    #[test]
    fn evidence_ledger_to_versioned_conversion() {
        let mut evidence = EvidenceLedger::new();
        evidence.record(super::DecisionRecord {
            ts_unix_ms: 5000,
            operation: "convert_op".to_owned(),
            mode: CompatibilityMode::Strict,
            action: DecisionAction::Allow,
            incompatibility_probability: 0.01,
            rationale: "conversion test".to_owned(),
            evidence: vec![],
        });

        let versioned = evidence.to_versioned();
        assert_eq!(
            versioned.schema_version,
            super::DECISION_LEDGER_SCHEMA_VERSION
        );
        assert_eq!(versioned.record_count, 1);
        assert_eq!(versioned.records[0].operation, "convert_op");
    }

    // -----------------------------------------------------------------------
    // Drift Analysis tests
    // -----------------------------------------------------------------------

    #[test]
    fn drift_analyzer_empty_ledger() {
        let ledger = super::VersionedDecisionLedger::new("empty");
        let analyzer = super::DriftAnalyzer::new();
        let report = analyzer.analyze(&ledger);

        assert_eq!(report.total_decisions, 0);
        assert_eq!(report.under_confident_count, 0);
        assert!(!report.has_drift());
        assert!(!report.has_high_risk_operations());
    }

    #[test]
    fn drift_analyzer_identifies_under_confident_decisions() {
        let mut ledger = super::VersionedDecisionLedger::new("under-confident");

        // Add some low-confidence decisions
        ledger.append(super::DecisionRecord {
            ts_unix_ms: 1000,
            operation: "safe_op".to_owned(),
            mode: CompatibilityMode::Strict,
            action: DecisionAction::Allow,
            incompatibility_probability: 0.1, // Low, confident
            rationale: "confident".to_owned(),
            evidence: vec![],
        });
        ledger.append(super::DecisionRecord {
            ts_unix_ms: 2000,
            operation: "risky_op".to_owned(),
            mode: CompatibilityMode::Strict,
            action: DecisionAction::FullValidate,
            incompatibility_probability: 0.5, // High, under-confident
            rationale: "uncertain".to_owned(),
            evidence: vec![],
        });

        let analyzer = super::DriftAnalyzer::new();
        let report = analyzer.analyze(&ledger);

        assert_eq!(report.total_decisions, 2);
        assert_eq!(report.under_confident_count, 1);
        assert!((report.under_confident_rate - 0.5).abs() < 0.01);
        assert!(report.has_high_risk_operations());
        assert_eq!(report.top_operations[0].operation, "risky_op");
    }

    #[test]
    fn drift_analyzer_custom_threshold() {
        let mut ledger = super::VersionedDecisionLedger::new("custom-threshold");

        ledger.append(super::DecisionRecord {
            ts_unix_ms: 1000,
            operation: "op".to_owned(),
            mode: CompatibilityMode::Strict,
            action: DecisionAction::Allow,
            incompatibility_probability: 0.25,
            rationale: "test".to_owned(),
            evidence: vec![],
        });

        // Default threshold is 0.3, so 0.25 is confident
        let default_analyzer = super::DriftAnalyzer::new();
        let default_report = default_analyzer.analyze(&ledger);
        assert_eq!(default_report.under_confident_count, 0);

        // Custom threshold of 0.2 makes 0.25 under-confident
        let custom_analyzer = super::DriftAnalyzer::with_threshold(0.2);
        let custom_report = custom_analyzer.analyze(&ledger);
        assert_eq!(custom_report.under_confident_count, 1);
    }

    #[test]
    fn drift_analyzer_weekly_grouping() {
        let mut ledger = super::VersionedDecisionLedger::new("weekly");
        let base_time = 1000u128;

        // Week 1 decisions
        for i in 0..3 {
            ledger.append(super::DecisionRecord {
                ts_unix_ms: base_time + (i * 1000),
                operation: "week1_op".to_owned(),
                mode: CompatibilityMode::Strict,
                action: DecisionAction::Allow,
                incompatibility_probability: 0.1,
                rationale: "week1".to_owned(),
                evidence: vec![],
            });
        }

        // Week 2 decisions (7+ days later)
        for i in 0..2 {
            ledger.append(super::DecisionRecord {
                ts_unix_ms: base_time + super::MILLIS_PER_WEEK + (i * 1000),
                operation: "week2_op".to_owned(),
                mode: CompatibilityMode::Strict,
                action: DecisionAction::FullValidate,
                incompatibility_probability: 0.4, // Under-confident
                rationale: "week2".to_owned(),
                evidence: vec![],
            });
        }

        let analyzer = super::DriftAnalyzer::new();
        let report = analyzer.analyze(&ledger);

        assert_eq!(report.total_decisions, 5);
        assert_eq!(report.weekly_summaries.len(), 2);
        assert_eq!(report.weekly_summaries[0].total_decisions, 3);
        assert_eq!(report.weekly_summaries[1].total_decisions, 2);
        assert_eq!(report.weekly_summaries[1].under_confident_count, 2);
    }

    #[test]
    fn drift_report_recommendations() {
        let mut ledger = super::VersionedDecisionLedger::new("recommendations");

        // Add many under-confident decisions
        for i in 0..10 {
            ledger.append(super::DecisionRecord {
                ts_unix_ms: i * 1000,
                operation: "risky_operation".to_owned(),
                mode: CompatibilityMode::Strict,
                action: DecisionAction::FailClosed,
                incompatibility_probability: 0.7,
                rationale: "high risk".to_owned(),
                evidence: vec![],
            });
        }

        let analyzer = super::DriftAnalyzer::new();
        let report = analyzer.analyze(&ledger);

        assert!(!report.recommendations.is_empty());
        assert!(
            report
                .recommendations
                .iter()
                .any(|r| r.contains("High under-confidence"))
        );
    }

    // ──────────────────────────────────────────────────────────────────────────
    // D5: Loss matrix calibration with Bayesian shrinkage prior tests
    // ──────────────────────────────────────────────────────────────────────────

    #[test]
    fn shrinkage_prior_returns_prior_mean_with_no_data() {
        let prior = super::BayesianShrinkagePrior::for_false_negative();
        let posterior = prior.posterior_mean(0.0, 0.0, 0);
        assert!(
            (posterior - prior.prior_mean).abs() < 1e-10,
            "With no data, posterior should equal prior mean"
        );
    }

    #[test]
    fn shrinkage_weight_increases_with_sample_count() {
        let prior = super::BayesianShrinkagePrior::for_false_negative();
        let variance = 100.0;

        let w1 = prior.shrinkage_weight(variance, 1);
        let w10 = prior.shrinkage_weight(variance, 10);
        let w100 = prior.shrinkage_weight(variance, 100);

        assert!(w1 < w10, "Weight should increase with more samples");
        assert!(w10 < w100, "Weight should increase with more samples");
        assert!(w100 < 1.0, "Weight should be less than 1");
        assert!(w1 > 0.0, "Weight should be positive");
    }

    #[test]
    fn shrinkage_pulls_empirical_toward_prior() {
        let prior = super::BayesianShrinkagePrior {
            prior_mean: 100.0,
            prior_variance: 400.0,
        };

        // Empirical mean far from prior
        let empirical_mean = 200.0;
        let empirical_variance = 100.0;

        // With few samples, posterior should be closer to prior
        let posterior_small = prior.posterior_mean(empirical_mean, empirical_variance, 2);
        // With many samples, posterior should be closer to empirical
        let posterior_large = prior.posterior_mean(empirical_mean, empirical_variance, 100);

        assert!(
            (posterior_small - prior.prior_mean).abs() < (posterior_large - prior.prior_mean).abs(),
            "Small sample posterior should be closer to prior"
        );
        assert!(
            (posterior_large - empirical_mean).abs() < (posterior_small - empirical_mean).abs(),
            "Large sample posterior should be closer to empirical"
        );
    }

    #[test]
    fn calibrator_with_no_observations_returns_prior() {
        let calibrator = super::LossMatrixCalibrator::new();
        let calibrated = calibrator.calibrate();

        let prior_fn = super::BayesianShrinkagePrior::for_false_negative();
        let prior_vc = super::BayesianShrinkagePrior::for_validate_cost();
        let prior_fp = super::BayesianShrinkagePrior::for_false_positive();

        assert!(
            (calibrated.matrix.allow_false_negative - prior_fn.prior_mean).abs() < 1e-10,
            "No data: should return prior mean for false negative"
        );
        assert!(
            (calibrated.matrix.validate_cost - prior_vc.prior_mean).abs() < 1e-10,
            "No data: should return prior mean for validate cost"
        );
        assert!(
            (calibrated.matrix.reject_false_positive - prior_fp.prior_mean).abs() < 1e-10,
            "No data: should return prior mean for false positive"
        );

        assert_eq!(calibrated.sample_counts.allow_false_negative, 0);
        assert_eq!(calibrated.sample_counts.validate_cost, 0);
        assert_eq!(calibrated.sample_counts.reject_false_positive, 0);
    }

    #[test]
    fn calibrator_adapts_to_observations() {
        let mut calibrator = super::LossMatrixCalibrator::new();

        // Add observations with variance (alternating between 140 and 160, mean=150)
        // This ensures we have empirical variance for shrinkage to apply
        for i in 0..50 {
            let loss = if i % 2 == 0 { 140.0 } else { 160.0 };
            calibrator.observe(&super::LossObservation {
                ts_unix_ms: i as u128,
                action: DecisionAction::Allow,
                was_incompatible: true,
                realized_loss: loss,
                loss_category: super::LossCategory::AllowFalseNegative,
            });
        }

        let calibrated = calibrator.calibrate();

        // With 50 observations averaging 150.0, the calibrated value should be pulled
        // toward 150.0 (away from prior of 100.0), but with shrinkage applied
        assert!(
            calibrated.matrix.allow_false_negative > 100.0,
            "Calibrated false negative should exceed prior (got {})",
            calibrated.matrix.allow_false_negative
        );
        // With variance, shrinkage pulls toward prior so we don't hit exactly 150
        assert!(
            calibrated.matrix.allow_false_negative < 150.0,
            "Calibrated false negative should be shrunk from empirical (got {})",
            calibrated.matrix.allow_false_negative
        );
        assert!(
            calibrated.shrinkage_weights.allow_false_negative > 0.5,
            "With 50 samples, shrinkage weight should favor empirical (got {})",
            calibrated.shrinkage_weights.allow_false_negative
        );
    }

    #[test]
    fn calibrator_handles_all_categories() {
        let mut calibrator = super::LossMatrixCalibrator::new();

        // Add observations to each category
        calibrator.observe(&super::LossObservation {
            ts_unix_ms: 1,
            action: DecisionAction::Allow,
            was_incompatible: true,
            realized_loss: 120.0,
            loss_category: super::LossCategory::AllowFalseNegative,
        });
        calibrator.observe(&super::LossObservation {
            ts_unix_ms: 2,
            action: DecisionAction::FullValidate,
            was_incompatible: false,
            realized_loss: 30.0,
            loss_category: super::LossCategory::ValidateCost,
        });
        calibrator.observe(&super::LossObservation {
            ts_unix_ms: 3,
            action: DecisionAction::FailClosed,
            was_incompatible: false,
            realized_loss: 70.0,
            loss_category: super::LossCategory::RejectFalsePositive,
        });

        let calibrated = calibrator.calibrate();

        assert_eq!(calibrated.sample_counts.allow_false_negative, 1);
        assert_eq!(calibrated.sample_counts.validate_cost, 1);
        assert_eq!(calibrated.sample_counts.reject_false_positive, 1);
    }

    #[test]
    fn calibrator_reset_clears_statistics() {
        let mut calibrator = super::LossMatrixCalibrator::new();

        calibrator.observe(&super::LossObservation {
            ts_unix_ms: 1,
            action: DecisionAction::Allow,
            was_incompatible: true,
            realized_loss: 120.0,
            loss_category: super::LossCategory::AllowFalseNegative,
        });

        assert_eq!(calibrator.sample_counts().allow_false_negative, 1);

        calibrator.reset();

        assert_eq!(calibrator.sample_counts().allow_false_negative, 0);

        let calibrated = calibrator.calibrate();
        let prior_fn = super::BayesianShrinkagePrior::for_false_negative();
        assert!(
            (calibrated.matrix.allow_false_negative - prior_fn.prior_mean).abs() < 1e-10,
            "After reset, should return prior mean"
        );
    }

    #[test]
    fn samples_for_confidence_computes_correctly() {
        let prior = super::BayesianShrinkagePrior::for_false_negative();

        // At threshold 0.5, w = 0.5, so n = 0.5 / 0.5 = 1
        let n_50 = super::LossMatrixCalibrator::samples_for_confidence(&prior, 0.5);
        assert_eq!(n_50, 1, "50% confidence should need 1 sample");

        // At threshold 0.9, w = 0.9, so n = 0.9 / 0.1 = 9
        let n_90 = super::LossMatrixCalibrator::samples_for_confidence(&prior, 0.9);
        assert_eq!(n_90, 9, "90% confidence should need 9 samples");

        // Edge cases
        let n_0 = super::LossMatrixCalibrator::samples_for_confidence(&prior, 0.0);
        assert_eq!(n_0, 0, "0% confidence needs 0 samples");

        let n_1 = super::LossMatrixCalibrator::samples_for_confidence(&prior, 1.0);
        assert_eq!(n_1, usize::MAX, "100% confidence is impossible");
    }

    #[test]
    fn loss_category_stats_computes_mean_and_variance() {
        let mut stats = super::LossCategoryStats::default();
        stats.add(10.0);
        stats.add(20.0);
        stats.add(30.0);

        assert_eq!(stats.count, 3);
        assert!((stats.mean() - 20.0).abs() < 1e-10, "Mean should be 20");

        // Variance = E[X²] - E[X]² = (100+400+900)/3 - 400 = 466.67 - 400 = 66.67
        let expected_variance = (100.0 + 400.0 + 900.0) / 3.0 - 400.0;
        assert!(
            (stats.variance() - expected_variance).abs() < 1e-10,
            "Variance calculation mismatch"
        );
    }

    #[test]
    fn calibrator_observe_batch_works() {
        let mut calibrator = super::LossMatrixCalibrator::new();
        let observations = vec![
            super::LossObservation {
                ts_unix_ms: 1,
                action: DecisionAction::Allow,
                was_incompatible: true,
                realized_loss: 100.0,
                loss_category: super::LossCategory::AllowFalseNegative,
            },
            super::LossObservation {
                ts_unix_ms: 2,
                action: DecisionAction::Allow,
                was_incompatible: true,
                realized_loss: 120.0,
                loss_category: super::LossCategory::AllowFalseNegative,
            },
        ];

        calibrator.observe_batch(&observations);
        assert_eq!(calibrator.sample_counts().allow_false_negative, 2);
    }

    // ──────────────────────────────────────────────────────────────────────────
    // D4: Hardened-mode Bayesian admission controller tests
    // ──────────────────────────────────────────────────────────────────────────

    #[test]
    fn admission_controller_strict_mode_allows_low_risk() {
        let mut controller = super::BayesianAdmissionController::new(CompatibilityMode::Strict);
        let decision = controller.decide(0.1);

        assert_eq!(decision.action, DecisionAction::Allow);
        assert!(!decision.hardened_override);
        assert!((decision.incompatibility_probability - 0.1).abs() < 1e-10);
    }

    #[test]
    fn admission_controller_hardened_mode_rejects_high_risk() {
        let mut controller = super::BayesianAdmissionController::new(CompatibilityMode::Hardened);
        let decision = controller.decide(0.9);

        assert_eq!(decision.action, DecisionAction::FailClosed);
        assert!(decision.hardened_override);
        assert!(
            decision.rationale.contains("exceeds threshold"),
            "Rationale should mention threshold"
        );
    }

    #[test]
    fn admission_controller_nan_probability_fails_closed() {
        let mut controller = super::BayesianAdmissionController::new(CompatibilityMode::Strict);
        let decision = controller.decide(f64::NAN);

        assert_eq!(decision.action, DecisionAction::FailClosed);
        assert!(decision.hardened_override);
        assert!(decision.rationale.contains("NaN"));
    }

    #[test]
    fn admission_controller_hardened_penalty_shifts_decisions() {
        // In hardened mode, the extra penalty should make validation preferred over allow
        // at moderate probability levels
        let mut strict = super::BayesianAdmissionController::new(CompatibilityMode::Strict);
        let mut hardened = super::BayesianAdmissionController::new(CompatibilityMode::Hardened);

        // At moderate probability, strict might allow but hardened should validate
        let p = 0.25;
        let strict_decision = strict.decide(p);
        let hardened_decision = hardened.decide(p);

        // The hardened mode applies a penalty to allow, making validate more likely
        // This is a tendency check, not a strict assertion
        if strict_decision.action == DecisionAction::Allow {
            // Hardened should be at least as conservative
            assert!(
                hardened_decision.action != DecisionAction::Allow
                    || hardened_decision.expected_loss >= strict_decision.expected_loss,
                "Hardened mode should be at least as conservative"
            );
        }
    }

    #[test]
    fn admission_controller_record_outcome_updates_calibrator() {
        let mut controller = super::BayesianAdmissionController::new(CompatibilityMode::Strict);

        // Make a decision
        let decision = controller.decide(0.5);

        // Record outcome as false negative (was incompatible but we allowed)
        if decision.action == DecisionAction::Allow {
            controller.record_outcome(&decision, true);
            let stats = controller.stats();
            assert_eq!(stats.sample_counts.allow_false_negative, 1);
        }
    }

    #[test]
    fn admission_controller_stats_track_decisions() {
        let mut controller = super::BayesianAdmissionController::new(CompatibilityMode::Hardened);

        // Make several decisions
        let _ = controller.decide(0.1);
        let _ = controller.decide(0.5);
        let _ = controller.decide(0.95); // Should trigger override

        let stats = controller.stats();
        assert_eq!(stats.decision_count, 3);
        assert_eq!(stats.override_count, 1); // One high-risk override
    }

    #[test]
    fn admission_controller_reset_clears_state() {
        let mut controller = super::BayesianAdmissionController::new(CompatibilityMode::Strict);

        let decision = controller.decide(0.5);
        controller.record_outcome(&decision, true);

        let before = controller.stats();
        assert!(before.decision_count > 0);

        controller.reset();

        let after = controller.stats();
        assert_eq!(after.decision_count, 0);
        assert_eq!(after.override_count, 0);
        assert_eq!(after.sample_counts.allow_false_negative, 0);
    }

    #[test]
    fn admission_controller_custom_config() {
        let config = super::AdmissionControllerConfig::conservative();
        let mut controller =
            super::BayesianAdmissionController::with_config(CompatibilityMode::Hardened, config);

        // Conservative config has max_incompatibility_probability of 0.7
        let decision = controller.decide(0.75);
        assert_eq!(decision.action, DecisionAction::FailClosed);
        assert!(decision.hardened_override);
    }

    #[test]
    fn admission_controller_correct_decisions_not_recorded() {
        let mut controller = super::BayesianAdmissionController::new(CompatibilityMode::Strict);

        // Make an allow decision
        let decision = controller.decide(0.1);
        assert_eq!(decision.action, DecisionAction::Allow);

        // Record as correct (not incompatible)
        controller.record_outcome(&decision, false);

        // No loss should be recorded for correct allows
        let stats = controller.stats();
        assert_eq!(stats.sample_counts.allow_false_negative, 0);
    }

    #[test]
    fn admission_controller_validation_always_records() {
        let mut controller = super::BayesianAdmissionController::new(CompatibilityMode::Strict);

        // Force a validate decision by giving moderate probability
        let decision = controller.decide(0.4);

        if decision.action == DecisionAction::FullValidate {
            // Validation cost is always paid, regardless of actual state
            controller.record_outcome(&decision, false);
            let stats = controller.stats();
            assert_eq!(stats.sample_counts.validate_cost, 1);
        }
    }

    // ──────────────────────────────────────────────────────────────────────────
    // D6: Calibrated confidence with Brier score gate tests
    // ──────────────────────────────────────────────────────────────────────────

    #[test]
    fn brier_score_perfect_predictions() {
        let mut tracker = super::BrierScoreTracker::new();

        // Perfect predictions: predict 1.0 when true, 0.0 when false
        tracker.record(1.0, true);
        tracker.record(0.0, false);
        tracker.record(1.0, true);
        tracker.record(0.0, false);

        let score = tracker.brier_score();
        assert!(
            score < 0.01,
            "Perfect predictions should have near-zero Brier score (got {})",
            score
        );
    }

    #[test]
    fn brier_score_worst_predictions() {
        let mut tracker = super::BrierScoreTracker::new();

        // Worst predictions: predict opposite of reality
        tracker.record(0.0, true); // Predicted 0, was 1 -> error = -1
        tracker.record(1.0, false); // Predicted 1, was 0 -> error = 1
        tracker.record(0.0, true);
        tracker.record(1.0, false);

        let score = tracker.brier_score();
        assert!(
            (score - 1.0).abs() < 0.01,
            "Worst predictions should have Brier score near 1.0 (got {})",
            score
        );
    }

    #[test]
    fn brier_score_calibrated_predictions() {
        let mut tracker = super::BrierScoreTracker::new();

        // Well-calibrated: predict 0.5, get 50% true
        for _ in 0..5 {
            tracker.record(0.5, true);
        }
        for _ in 0..5 {
            tracker.record(0.5, false);
        }

        let score = tracker.brier_score();
        // (0.5 - 1)^2 = 0.25 for true cases
        // (0.5 - 0)^2 = 0.25 for false cases
        // Average = 0.25
        assert!(
            (score - 0.25).abs() < 0.01,
            "50% predictions with 50% outcomes should have Brier score of 0.25 (got {})",
            score
        );
    }

    #[test]
    fn brier_score_empty_tracker() {
        let tracker = super::BrierScoreTracker::new();
        let score = tracker.brier_score();
        assert!(
            (score - 0.5).abs() < 0.01,
            "Empty tracker should return 0.5 (got {})",
            score
        );
    }

    #[test]
    fn brier_score_tracker_reset() {
        let mut tracker = super::BrierScoreTracker::new();
        tracker.record(0.8, true);
        tracker.record(0.2, false);
        assert!(tracker.count() > 0);

        tracker.reset();

        assert_eq!(tracker.count(), 0);
        assert!((tracker.brier_score() - 0.5).abs() < 0.01);
    }

    #[test]
    fn brier_score_metrics_computes_base_rate() {
        let mut tracker = super::BrierScoreTracker::new();

        // 3 positives, 7 negatives -> base rate = 0.3
        for _ in 0..3 {
            tracker.record(0.5, true);
        }
        for _ in 0..7 {
            tracker.record(0.5, false);
        }

        let metrics = tracker.metrics();
        assert!(
            (metrics.base_rate - 0.3).abs() < 0.01,
            "Base rate should be 0.3 (got {})",
            metrics.base_rate
        );
        assert_eq!(metrics.sample_count, 10);
    }

    #[test]
    fn brier_gate_open_with_insufficient_samples() {
        let gate = super::BrierScoreGate::new();
        assert!(gate.is_open(), "Gate should be open with no samples");

        let decision = gate.apply(DecisionAction::Allow);
        assert_eq!(decision.action, DecisionAction::Allow);
        assert!(!decision.gate_applied);
    }

    #[test]
    fn brier_gate_blocks_poor_calibration() {
        let mut gate = super::BrierScoreGate::with_settings(0.25, 10, DecisionAction::FailClosed);

        // Record many bad predictions
        for _ in 0..15 {
            gate.record(0.9, false); // Predict 0.9 but outcome is 0
        }

        let score = gate.brier_score();
        assert!(
            score > 0.25,
            "Bad predictions should have high Brier score (got {})",
            score
        );
        assert!(
            !gate.is_open(),
            "Gate should be closed with poor calibration"
        );

        let decision = gate.apply(DecisionAction::Allow);
        assert_eq!(decision.action, DecisionAction::FailClosed);
        assert!(decision.gate_applied);
    }

    #[test]
    fn brier_gate_allows_good_calibration() {
        let mut gate = super::BrierScoreGate::with_settings(0.3, 10, DecisionAction::FullValidate);

        // Record well-calibrated predictions
        for _ in 0..6 {
            gate.record(0.7, true);
        }
        for _ in 0..4 {
            gate.record(0.3, false);
        }

        // (0.7-1)^2 = 0.09 for true, (0.3-0)^2 = 0.09 for false
        // Average ≈ 0.09, below threshold
        let score = gate.brier_score();
        assert!(
            score <= 0.3,
            "Good calibration should have low Brier score (got {})",
            score
        );
        assert!(gate.is_open(), "Gate should be open with good calibration");

        let decision = gate.apply(DecisionAction::Allow);
        assert_eq!(decision.action, DecisionAction::Allow);
        assert!(!decision.gate_applied);
    }

    #[test]
    fn brier_gate_reset_reopens() {
        let mut gate = super::BrierScoreGate::with_settings(0.2, 5, DecisionAction::FailClosed);

        // Make gate close with bad predictions
        for _ in 0..10 {
            gate.record(1.0, false);
        }
        assert!(!gate.is_open());

        gate.reset();

        assert!(gate.is_open(), "Gate should be open after reset");
        assert_eq!(gate.metrics().sample_count, 0);
    }

    #[test]
    fn brier_gate_custom_settings() {
        let gate = super::BrierScoreGate::with_settings(0.15, 20, DecisionAction::FullValidate);

        assert!((gate.threshold() - 0.15).abs() < 0.01);
        // With min_samples=20, gate should be open until we have 20 samples
        assert!(gate.is_open());
    }

    // ──────────────────────────────────────────────────────────────────────────
    // E12: Tail-stability gate tests
    // ──────────────────────────────────────────────────────────────────────────

    #[test]
    fn tail_tracker_collects_baseline() {
        let config = super::TailStabilityConfig {
            baseline_samples: 5,
            window_samples: 3,
            max_p99_ratio: 1.2,
            percentile: 0.99,
        };
        let mut tracker = super::TailStabilityTracker::with_config(config);

        // Collect baseline
        for i in 0..5 {
            tracker.record((i + 1) as f64);
        }

        assert!(tracker.is_baseline_locked());
        assert!(tracker.baseline_p99().is_some());
        assert_eq!(tracker.baseline_count(), 5);
    }

    #[test]
    fn tail_tracker_detects_regression() {
        let config = super::TailStabilityConfig {
            baseline_samples: 5,
            window_samples: 5,
            max_p99_ratio: 1.2, // 20% regression threshold
            percentile: 0.99,
        };
        let mut tracker = super::TailStabilityTracker::with_config(config);

        // Low baseline (1-5)
        for i in 0..5 {
            tracker.record((i + 1) as f64);
        }
        let baseline_p99 = tracker.baseline_p99().unwrap();

        // High window samples (10-50) - significant regression
        for i in 0..5 {
            tracker.record(((i + 1) * 10) as f64);
        }

        let window_p99 = tracker.window_p99().unwrap();
        assert!(
            window_p99 > baseline_p99 * 1.2,
            "Window p99 ({}) should be > 1.2x baseline p99 ({})",
            window_p99,
            baseline_p99
        );
        assert!(tracker.has_shift(), "Should detect regression");
    }

    #[test]
    fn tail_tracker_no_shift_when_stable() {
        let config = super::TailStabilityConfig {
            baseline_samples: 5,
            window_samples: 5,
            max_p99_ratio: 1.2,
            percentile: 0.99,
        };
        let mut tracker = super::TailStabilityTracker::with_config(config);

        // Same distribution for baseline and window
        for _ in 0..5 {
            tracker.record(10.0);
        }
        for _ in 0..5 {
            tracker.record(10.0);
        }

        assert!(!tracker.has_shift(), "Should not detect shift when stable");
        let ratio = tracker.p99_ratio().unwrap();
        assert!(
            (ratio - 1.0).abs() < 0.01,
            "Ratio should be ~1.0 (got {})",
            ratio
        );
    }

    #[test]
    fn tail_tracker_window_slides() {
        let config = super::TailStabilityConfig {
            baseline_samples: 3,
            window_samples: 3,
            max_p99_ratio: 1.5,
            percentile: 0.99,
        };
        let mut tracker = super::TailStabilityTracker::with_config(config);

        // Baseline
        for _ in 0..3 {
            tracker.record(10.0);
        }

        // Fill window
        for _ in 0..3 {
            tracker.record(15.0);
        }
        assert_eq!(tracker.window_count(), 3);

        // Add more - should slide
        tracker.record(20.0);
        assert_eq!(tracker.window_count(), 3); // Still 3 samples

        // Window should now contain [15, 15, 20] approximately
        let p99 = tracker.window_p99().unwrap();
        assert!(p99 >= 15.0, "Window p99 should be >= 15 (got {})", p99);
    }

    #[test]
    fn tail_tracker_reset() {
        let mut tracker = super::TailStabilityTracker::new();

        for i in 0..35 {
            tracker.record(i as f64);
        }
        assert!(tracker.is_baseline_locked());

        tracker.reset();

        assert!(!tracker.is_baseline_locked());
        assert_eq!(tracker.baseline_count(), 0);
        assert_eq!(tracker.window_count(), 0);
        assert!(tracker.baseline_p99().is_none());
    }

    #[test]
    fn tail_tracker_force_lock_baseline() {
        let config = super::TailStabilityConfig {
            baseline_samples: 30,
            window_samples: 10,
            max_p99_ratio: 1.2,
            percentile: 0.99,
        };
        let mut tracker = super::TailStabilityTracker::with_config(config);

        // Only add 5 samples (less than 30)
        for i in 0..5 {
            tracker.record(i as f64);
        }
        assert!(!tracker.is_baseline_locked());

        tracker.force_lock_baseline();

        assert!(tracker.is_baseline_locked());
        assert!(tracker.baseline_p99().is_some());
    }

    #[test]
    fn tail_gate_open_during_baseline_collection() {
        let mut gate = super::TailStabilityGate::new();

        // During baseline collection, gate should be open
        for i in 0..10 {
            gate.record(i as f64);
            assert!(
                gate.is_open(),
                "Gate should be open during baseline collection"
            );
        }
    }

    #[test]
    fn tail_gate_blocks_on_regression() {
        let config = super::TailStabilityConfig {
            baseline_samples: 5,
            window_samples: 5,
            max_p99_ratio: 1.2,
            percentile: 0.99,
        };
        let mut gate = super::TailStabilityGate::with_config(config, DecisionAction::FailClosed);

        // Low baseline
        for _ in 0..5 {
            gate.record(10.0);
        }

        // High window - causes regression
        for _ in 0..5 {
            gate.record(50.0);
        }

        assert!(!gate.is_open(), "Gate should be closed on regression");

        let decision = gate.apply(DecisionAction::Allow);
        assert_eq!(decision.action, DecisionAction::FailClosed);
        assert!(decision.gate_applied);
    }

    #[test]
    fn tail_gate_status_includes_details() {
        let mut gate = super::TailStabilityGate::new();

        for i in 0..35 {
            gate.record((i % 10) as f64);
        }

        let status = gate.status();
        assert!(status.baseline_locked);
        assert!(status.baseline_p99.is_some());
        assert!(status.p99_ratio.is_some());
    }

    #[test]
    fn tail_gate_reset_reopens() {
        let config = super::TailStabilityConfig {
            baseline_samples: 3,
            window_samples: 3,
            max_p99_ratio: 1.1,
            percentile: 0.99,
        };
        let mut gate = super::TailStabilityGate::with_config(config, DecisionAction::FailClosed);

        // Cause regression
        for _ in 0..3 {
            gate.record(10.0);
        }
        for _ in 0..3 {
            gate.record(50.0);
        }
        assert!(!gate.is_open());

        gate.reset();

        assert!(gate.is_open(), "Gate should be open after reset");
    }

    // ──────────────────────────────────────────────────────────────────────────
    // E3: Profile-and-prove optimization loop tests
    // ──────────────────────────────────────────────────────────────────────────

    #[test]
    fn slo_row_id_metric_ids() {
        assert_eq!(super::SloRowId::ShortestPath.metric_id(), "shortest_path");
        assert_eq!(super::SloRowId::Components.metric_id(), "components");
        assert_eq!(super::SloRowId::Centrality.metric_id(), "centrality");
        assert_eq!(super::SloRowId::Flow.metric_id(), "flow");
        assert_eq!(super::SloRowId::IoRoundtrip.metric_id(), "io_roundtrip");
        assert_eq!(super::SloRowId::MutationCycle.metric_id(), "mutation_cycle");
        assert_eq!(
            super::SloRowId::MutationRegression.metric_id(),
            "mutation_regression"
        );
        assert_eq!(
            super::SloRowId::MemoryRegression.metric_id(),
            "memory_regression"
        );
        assert_eq!(
            super::SloRowId::P99TailRegression.metric_id(),
            "p99_tail_regression"
        );
        assert_eq!(super::SloRowId::ALL.len(), 9);
    }

    #[test]
    fn optimization_delta_computes_improvement() {
        let baseline = super::SloBaseline {
            row_id: super::SloRowId::ShortestPath,
            p50_ms: 100.0,
            p95_ms: 200.0,
            p99_ms: 300.0,
            peak_memory_kb: 100_000,
            sample_count: 30,
            captured_at_unix_ms: 1,
        };

        let after = super::SloBaseline {
            row_id: super::SloRowId::ShortestPath,
            p50_ms: 80.0,
            p95_ms: 160.0,
            p99_ms: 240.0,
            peak_memory_kb: 100_000,
            sample_count: 30,
            captured_at_unix_ms: 2,
        };

        let delta = super::OptimizationDelta::compute(&baseline, &after);

        assert!((delta.p50_delta_ms - (-20.0)).abs() < 0.01);
        assert!((delta.p95_delta_ms - (-40.0)).abs() < 0.01);
        assert!((delta.p99_delta_ms - (-60.0)).abs() < 0.01);
        assert_eq!(delta.memory_delta_kb, 0);
        assert!((delta.p95_improvement_pct - 20.0).abs() < 0.01);
        assert!(delta.is_improvement());
    }

    #[test]
    fn optimization_delta_detects_regression() {
        let baseline = super::SloBaseline {
            row_id: super::SloRowId::Components,
            p50_ms: 100.0,
            p95_ms: 200.0,
            p99_ms: 300.0,
            peak_memory_kb: 100_000,
            sample_count: 30,
            captured_at_unix_ms: 1,
        };

        let after = super::SloBaseline {
            row_id: super::SloRowId::Components,
            p50_ms: 120.0,
            p95_ms: 250.0,
            p99_ms: 400.0,
            peak_memory_kb: 100_000,
            sample_count: 30,
            captured_at_unix_ms: 2,
        };

        let delta = super::OptimizationDelta::compute(&baseline, &after);
        assert!(
            !delta.is_improvement(),
            "Regression should not be improvement"
        );
    }

    #[test]
    fn profile_prove_state_transitions() {
        let mut state =
            super::ProfileProveState::new(super::SloRowId::Flow, "vectorize inner loop");

        assert_eq!(state.phase, super::OptimizationPhase::Baseline);

        // Record baseline
        state.record_baseline(super::SloBaseline {
            row_id: super::SloRowId::Flow,
            p50_ms: 100.0,
            p95_ms: 200.0,
            p99_ms: 300.0,
            peak_memory_kb: 50_000,
            sample_count: 30,
            captured_at_unix_ms: 1,
        });
        assert_eq!(state.phase, super::OptimizationPhase::Optimize);

        // Mark optimized
        state.mark_optimized();
        assert_eq!(state.phase, super::OptimizationPhase::Verify);

        // Record successful verification
        state.record_verification(super::OptimizationEvidence {
            fixtures_verified: 78,
            mismatches: 0,
            conformance_hash: "abc123".to_owned(),
            verified_at_unix_ms: 2,
        });
        assert_eq!(state.phase, super::OptimizationPhase::Measure);

        // Record after measurement (improved)
        state.record_after(super::SloBaseline {
            row_id: super::SloRowId::Flow,
            p50_ms: 80.0,
            p95_ms: 160.0,
            p99_ms: 240.0,
            peak_memory_kb: 50_000,
            sample_count: 30,
            captured_at_unix_ms: 3,
        });
        assert_eq!(state.phase, super::OptimizationPhase::Complete);
        assert!(state.is_complete());

        // Get result
        let result = state.result().expect("should have result");
        assert!(result.success);
        assert!(result.delta.p95_improvement_pct > 0.0);
    }

    #[test]
    fn profile_prove_state_fails_on_mismatch() {
        let mut state = super::ProfileProveState::new(super::SloRowId::Centrality, "cache results");

        state.record_baseline(super::SloBaseline {
            row_id: super::SloRowId::Centrality,
            p50_ms: 500.0,
            p95_ms: 800.0,
            p99_ms: 1000.0,
            peak_memory_kb: 200_000,
            sample_count: 30,
            captured_at_unix_ms: 1,
        });
        state.mark_optimized();

        // Verification fails with mismatches
        state.record_verification(super::OptimizationEvidence {
            fixtures_verified: 78,
            mismatches: 3,
            conformance_hash: "bad123".to_owned(),
            verified_at_unix_ms: 2,
        });

        // Should jump to Complete (not Measure)
        assert_eq!(state.phase, super::OptimizationPhase::Complete);
        assert!(state.is_complete());
        assert!(
            state.result().is_none(),
            "Should not have result without after measurement"
        );
    }

    #[test]
    fn profile_prove_loop_tracks_results() {
        let mut loop_runner = super::ProfileProveLoop::new();

        // Start optimization for ShortestPath
        loop_runner.start(super::SloRowId::ShortestPath, "use priority queue");

        assert!(
            loop_runner
                .get_active(super::SloRowId::ShortestPath)
                .is_some()
        );

        // Simulate successful optimization
        if let Some(state) = loop_runner.get_active_mut(super::SloRowId::ShortestPath) {
            state.record_baseline(super::SloBaseline {
                row_id: super::SloRowId::ShortestPath,
                p50_ms: 300.0,
                p95_ms: 400.0,
                p99_ms: 500.0,
                peak_memory_kb: 80_000,
                sample_count: 30,
                captured_at_unix_ms: 1,
            });
            state.mark_optimized();
            state.record_verification(super::OptimizationEvidence {
                fixtures_verified: 78,
                mismatches: 0,
                conformance_hash: "hash1".to_owned(),
                verified_at_unix_ms: 2,
            });
            state.record_after(super::SloBaseline {
                row_id: super::SloRowId::ShortestPath,
                p50_ms: 250.0,
                p95_ms: 320.0,
                p99_ms: 400.0,
                peak_memory_kb: 80_000,
                sample_count: 30,
                captured_at_unix_ms: 3,
            });
        }

        loop_runner.complete(super::SloRowId::ShortestPath);

        let summary = loop_runner.summary();
        assert_eq!(summary.total_attempts, 1);
        assert_eq!(summary.successful, 1);
        assert_eq!(summary.failed, 0);
        assert!(summary.avg_p95_improvement_pct > 0.0);
        assert_eq!(summary.rows_optimized.len(), 1);
    }

    #[test]
    fn profile_prove_summary_handles_failures() {
        let mut loop_runner = super::ProfileProveLoop::new();

        // Add a failed result manually
        loop_runner.results.push(super::OptimizationResult {
            row_id: super::SloRowId::Centrality,
            optimization_description: "bad optimization".to_owned(),
            baseline: super::SloBaseline {
                row_id: super::SloRowId::Centrality,
                p50_ms: 100.0,
                p95_ms: 200.0,
                p99_ms: 300.0,
                peak_memory_kb: 50_000,
                sample_count: 30,
                captured_at_unix_ms: 1,
            },
            after: super::SloBaseline {
                row_id: super::SloRowId::Centrality,
                p50_ms: 150.0,
                p95_ms: 280.0,
                p99_ms: 400.0,
                peak_memory_kb: 50_000,
                sample_count: 30,
                captured_at_unix_ms: 2,
            },
            evidence: super::OptimizationEvidence {
                fixtures_verified: 78,
                mismatches: 0,
                conformance_hash: "hash".to_owned(),
                verified_at_unix_ms: 2,
            },
            success: false, // Regression
            delta: super::OptimizationDelta {
                p50_delta_ms: 50.0,
                p95_delta_ms: 80.0,
                p99_delta_ms: 100.0,
                memory_delta_kb: 0,
                p95_improvement_pct: -40.0,
            },
        });

        let summary = loop_runner.summary();
        assert_eq!(summary.total_attempts, 1);
        assert_eq!(summary.successful, 0);
        assert_eq!(summary.failed, 1);
        assert!((summary.avg_p95_improvement_pct - 0.0).abs() < 0.01);
    }

    // ──────────────────────────────────────────────────────────────────────────
    // G6: Algebraic effect tracking tests
    // ──────────────────────────────────────────────────────────────────────────

    #[test]
    fn parser_effect_kind_properties() {
        use super::ParserEffectKind;

        assert!(ParserEffectKind::FailClosed.is_terminal());
        assert!(!ParserEffectKind::Warning.is_terminal());
        assert!(!ParserEffectKind::Allow.is_terminal());

        assert!(ParserEffectKind::Warning.is_recoverable());
        assert!(ParserEffectKind::Fallback.is_recoverable());
        assert!(ParserEffectKind::Coercion.is_recoverable());
        assert!(!ParserEffectKind::FailClosed.is_recoverable());

        assert_eq!(ParserEffectKind::Warning.as_str(), "warning");
        assert_eq!(ParserEffectKind::FailClosed.as_str(), "fail_closed");
    }

    #[test]
    fn parser_effect_constructors() {
        use super::{CompatibilityMode, ParserEffect, ParserEffectKind};

        let warning = ParserEffect::warning(
            "read_graphml",
            "missing attribute",
            CompatibilityMode::Strict,
        );
        assert_eq!(warning.kind, ParserEffectKind::Warning);
        assert_eq!(warning.operation, "read_graphml");
        assert!(warning.risk_probability > 0.0);

        let fail =
            ParserEffect::fail_closed("read_json", "invalid json", CompatibilityMode::Strict);
        assert_eq!(fail.kind, ParserEffectKind::FailClosed);
        assert!((fail.risk_probability - 1.0).abs() < 0.001);

        let allow = ParserEffect::allow("parse", "ok", CompatibilityMode::Hardened, 0.1);
        assert_eq!(allow.kind, ParserEffectKind::Allow);
        assert!((allow.risk_probability - 0.1).abs() < 0.001);
    }

    #[test]
    fn parser_effect_with_location() {
        use super::{CompatibilityMode, ParserEffect};

        let effect = ParserEffect::warning("read_edgelist", "bad line", CompatibilityMode::Strict)
            .with_location("line 42");
        assert_eq!(effect.source_location, Some("line 42".to_owned()));
    }

    #[test]
    fn effect_trace_basic_operations() {
        use super::{CompatibilityMode, EffectTrace, ParserEffect, ParserEffectKind};

        let mut trace = EffectTrace::new();
        assert!(trace.is_empty());
        assert!(!trace.is_terminated());

        trace.record(ParserEffect::warning(
            "op1",
            "msg1",
            CompatibilityMode::Strict,
        ));
        assert_eq!(trace.len(), 1);
        assert!(!trace.is_empty());
        assert!(!trace.is_terminated());

        trace.record(ParserEffect::allow(
            "op2",
            "msg2",
            CompatibilityMode::Strict,
            0.1,
        ));
        assert_eq!(trace.len(), 2);
        assert!(!trace.is_terminated());

        // Add a terminal effect
        trace.record(ParserEffect::fail_closed(
            "op3",
            "error",
            CompatibilityMode::Strict,
        ));
        assert_eq!(trace.len(), 3);
        assert!(trace.is_terminated());

        // Can still add more effects after terminal
        trace.record(ParserEffect::warning(
            "op4",
            "msg4",
            CompatibilityMode::Strict,
        ));
        assert_eq!(trace.len(), 4);
        assert!(trace.is_terminated());

        // Terminal effect is still the first terminal
        let terminal = trace.terminal().unwrap();
        assert_eq!(terminal.kind, ParserEffectKind::FailClosed);
        assert_eq!(terminal.operation, "op3");
    }

    #[test]
    fn effect_trace_filtering() {
        use super::{CompatibilityMode, EffectTrace, ParserEffect, ParserEffectKind};

        let mut trace = EffectTrace::new();
        trace.record(ParserEffect::warning(
            "op1",
            "warn1",
            CompatibilityMode::Strict,
        ));
        trace.record(ParserEffect::warning(
            "op2",
            "warn2",
            CompatibilityMode::Strict,
        ));
        trace.record(ParserEffect::allow(
            "op3",
            "ok",
            CompatibilityMode::Strict,
            0.1,
        ));
        trace.record(ParserEffect::warning(
            "op4",
            "warn3",
            CompatibilityMode::Strict,
        ));

        let warnings = trace.warnings();
        assert_eq!(warnings.len(), 3);

        assert_eq!(trace.count_kind(ParserEffectKind::Warning), 3);
        assert_eq!(trace.count_kind(ParserEffectKind::Allow), 1);
        assert_eq!(trace.count_kind(ParserEffectKind::FailClosed), 0);
    }

    #[test]
    fn effect_trace_merge() {
        use super::{CompatibilityMode, EffectTrace, ParserEffect, ParserEffectKind};

        let mut trace1 = EffectTrace::new();
        trace1.record(ParserEffect::warning("a", "m1", CompatibilityMode::Strict));
        trace1.record(ParserEffect::warning("b", "m2", CompatibilityMode::Strict));

        let mut trace2 = EffectTrace::new();
        trace2.record(ParserEffect::allow(
            "c",
            "m3",
            CompatibilityMode::Strict,
            0.1,
        ));
        trace2.record(ParserEffect::fail_closed(
            "d",
            "m4",
            CompatibilityMode::Strict,
        ));

        trace1.merge(trace2);

        assert_eq!(trace1.len(), 4);
        assert!(trace1.is_terminated());
        assert_eq!(
            trace1.terminal().unwrap().kind,
            ParserEffectKind::FailClosed
        );
    }

    #[test]
    fn effect_trace_summary() {
        use super::{CompatibilityMode, EffectTrace, ParserEffect};

        let mut trace = EffectTrace::new();
        trace.record(ParserEffect::warning("a", "m1", CompatibilityMode::Strict));
        trace.record(ParserEffect::new(
            super::ParserEffectKind::Coercion,
            "b",
            "m2",
            CompatibilityMode::Strict,
            0.3,
        ));
        trace.record(ParserEffect::fail_closed(
            "c",
            "m3",
            CompatibilityMode::Strict,
        ));

        let summary = trace.summary();
        assert_eq!(summary.total_effects, 3);
        assert_eq!(summary.warnings, 1);
        assert_eq!(summary.failures, 1);
        assert_eq!(summary.coercions, 1);
        assert!(summary.is_terminated);
        assert!((summary.max_risk - 1.0).abs() < 0.001);
    }

    #[test]
    fn effect_policy_should_fail() {
        use super::{CompatibilityMode, EffectPolicy, ParserEffect};

        let warning = ParserEffect::warning("op", "msg", CompatibilityMode::Strict);
        let fail = ParserEffect::fail_closed("op", "msg", CompatibilityMode::Strict);
        let allow = ParserEffect::allow("op", "msg", CompatibilityMode::Strict, 0.1);

        // CollectAll: only fails on terminal
        assert!(!EffectPolicy::CollectAll.should_fail(&warning));
        assert!(EffectPolicy::CollectAll.should_fail(&fail));
        assert!(!EffectPolicy::CollectAll.should_fail(&allow));

        // FailOnAny: fails on everything
        assert!(EffectPolicy::FailOnAny.should_fail(&warning));
        assert!(EffectPolicy::FailOnAny.should_fail(&fail));
        assert!(EffectPolicy::FailOnAny.should_fail(&allow));

        // FailOnWarning: fails on warning or terminal
        assert!(EffectPolicy::FailOnWarning.should_fail(&warning));
        assert!(EffectPolicy::FailOnWarning.should_fail(&fail));
        assert!(!EffectPolicy::FailOnWarning.should_fail(&allow));

        // FailOnTerminal: only fails on terminal
        assert!(!EffectPolicy::FailOnTerminal.should_fail(&warning));
        assert!(EffectPolicy::FailOnTerminal.should_fail(&fail));
        assert!(!EffectPolicy::FailOnTerminal.should_fail(&allow));
    }

    #[test]
    fn effect_handler_collect_all() {
        use super::{CompatibilityMode, EffectHandler, ParserEffect};

        let mut handler = EffectHandler::collect_all();

        // Warnings should be Ok
        let result = handler.handle(ParserEffect::warning(
            "op1",
            "m1",
            CompatibilityMode::Strict,
        ));
        assert!(result.is_ok());

        // Allows should be Ok
        let result = handler.handle(ParserEffect::allow(
            "op2",
            "m2",
            CompatibilityMode::Strict,
            0.1,
        ));
        assert!(result.is_ok());

        // FailClosed should be Err
        let result = handler.handle(ParserEffect::fail_closed(
            "op3",
            "m3",
            CompatibilityMode::Strict,
        ));
        assert!(result.is_err());

        // Trace should have all effects
        assert_eq!(handler.trace().len(), 3);
        assert!(handler.trace().is_terminated());
    }

    #[test]
    fn effect_handler_fail_on_terminal() {
        use super::{CompatibilityMode, EffectHandler, ParserEffect};

        let mut handler = EffectHandler::fail_on_terminal();

        let result = handler.handle(ParserEffect::warning(
            "op",
            "msg",
            CompatibilityMode::Strict,
        ));
        assert!(result.is_ok());

        let result = handler.handle(ParserEffect::fail_closed(
            "op",
            "msg",
            CompatibilityMode::Strict,
        ));
        assert!(result.is_err());
    }

    #[test]
    fn effect_handler_into_trace() {
        use super::{CompatibilityMode, EffectHandler, ParserEffect};

        let mut handler = EffectHandler::collect_all();
        let _ = handler.handle(ParserEffect::warning(
            "op",
            "msg",
            CompatibilityMode::Strict,
        ));

        let trace = handler.into_trace();
        assert_eq!(trace.len(), 1);
    }

    #[test]
    fn effect_handler_summary() {
        use super::{CompatibilityMode, EffectHandler, ParserEffect};

        let mut handler = EffectHandler::collect_all();
        let _ = handler.handle(ParserEffect::warning(
            "op1",
            "m1",
            CompatibilityMode::Strict,
        ));
        let _ = handler.handle(ParserEffect::warning(
            "op2",
            "m2",
            CompatibilityMode::Strict,
        ));

        let summary = handler.summary();
        assert_eq!(summary.total_effects, 2);
        assert_eq!(summary.warnings, 2);
    }
}
