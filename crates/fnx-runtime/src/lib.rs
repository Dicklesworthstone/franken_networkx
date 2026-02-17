#![forbid(unsafe_code)]

use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};
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
        if checkpoint.attempt > intent.max_attempts {
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
        let base = u64::try_from(self.transitions.len())
            .expect("transition log length should fit into u64");
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
            TestStatus::Skipped => "failed_closed",
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

#[cfg(test)]
mod tests {
    use super::{
        AsupersyncAdapterMachine, AsupersyncAdapterReasonCode, AsupersyncAdapterState,
        AsupersyncTransferIntent, CompatibilityMode, DecisionAction, E2eStepStatus, E2eStepTrace,
        EvidenceLedger, FailureReproData, ForensicsBundleIndex, FtuiTelemetryAdapter,
        StructuredTestLog, TestKind, TestStatus, canonical_environment_fingerprint,
        decision_theoretic_action, ftui_telemetry_canonical_fields,
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
}
