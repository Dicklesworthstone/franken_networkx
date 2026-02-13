#![forbid(unsafe_code)]

use serde::{Deserialize, Serialize};
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
    use super::{CompatibilityMode, DecisionAction, EvidenceLedger, decision_theoretic_action};

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
}
