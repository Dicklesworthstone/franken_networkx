use serde_json::Value;
use std::collections::BTreeSet;
use std::fs;
use std::path::{Path, PathBuf};

fn repo_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..")
}

fn load_json(path: &Path) -> Value {
    let raw = fs::read_to_string(path)
        .unwrap_or_else(|err| panic!("expected readable json at {}: {err}", path.display()));
    serde_json::from_str(&raw)
        .unwrap_or_else(|err| panic!("expected valid json at {}: {err}", path.display()))
}

fn required_string_array<'a>(schema: &'a Value, key: &str) -> Vec<&'a str> {
    schema[key]
        .as_array()
        .unwrap_or_else(|| panic!("schema key `{key}` should be array"))
        .iter()
        .map(|value| {
            value
                .as_str()
                .unwrap_or_else(|| panic!("schema key `{key}` entry should be string"))
        })
        .collect()
}

fn assert_path(path: &str, ctx: &str, root: &Path) {
    assert!(
        !path.trim().is_empty(),
        "{ctx} should be non-empty path string"
    );
    let full = root.join(path);
    assert!(full.exists(), "{ctx} path missing: {}", full.display());
}

#[test]
fn clean_final_compliance_attestation_is_complete_and_signoff_ready() {
    let root = repo_root();
    let artifact_path = "artifacts/clean/v1/clean_final_compliance_attestation_v1.json";
    let schema_path = "artifacts/clean/schema/v1/clean_final_compliance_attestation_schema_v1.json";
    let validation_path =
        "artifacts/clean/latest/clean_final_compliance_attestation_validation_v1.json";

    let artifact = load_json(&root.join(artifact_path));
    let schema = load_json(&root.join(schema_path));
    let validation = load_json(&root.join(validation_path));

    for key in required_string_array(&schema, "required_top_level_keys") {
        assert!(
            artifact.get(key).is_some(),
            "artifact missing top-level key `{key}`"
        );
    }

    let compliance_inputs = artifact["compliance_inputs"]
        .as_object()
        .expect("compliance_inputs should be object");
    for key in required_string_array(&schema, "required_compliance_input_keys") {
        assert!(
            compliance_inputs.get(key).is_some(),
            "compliance_inputs missing key `{key}`"
        );
    }
    for key in [
        "provenance_ledger",
        "unsafe_policy_registry",
        "safety_gate_pipeline",
        "compliance_audit_log",
    ] {
        let path = compliance_inputs[key]
            .as_str()
            .unwrap_or_else(|| panic!("compliance_inputs.{key} should be string"));
        assert_path(path, &format!("compliance_inputs.{key}"), &root);
    }
    for key in [
        "validation_reports",
        "conformance_traceability",
        "isomorphism_proofs",
    ] {
        let entries = compliance_inputs[key]
            .as_array()
            .unwrap_or_else(|| panic!("compliance_inputs.{key} should be array"));
        assert!(
            !entries.is_empty(),
            "compliance_inputs.{key} should be non-empty"
        );
        for (idx, value) in entries.iter().enumerate() {
            let path = value
                .as_str()
                .unwrap_or_else(|| panic!("compliance_inputs.{key}[{idx}] should be path string"));
            assert_path(path, &format!("compliance_inputs.{key}[{idx}]"), &root);
        }
    }

    let durability = artifact["durability_evidence"]
        .as_object()
        .expect("durability_evidence should be object");
    for key in required_string_array(&schema, "required_durability_keys") {
        assert!(
            durability.get(key).is_some(),
            "durability_evidence missing key `{key}`"
        );
    }

    let sidecars = durability["raptorq_sidecars"]
        .as_array()
        .expect("durability_evidence.raptorq_sidecars should be array");
    assert!(
        !sidecars.is_empty(),
        "durability_evidence.raptorq_sidecars should be non-empty"
    );
    for (idx, entry) in sidecars.iter().enumerate() {
        let path = entry.as_str().unwrap_or_else(|| {
            panic!("durability_evidence.raptorq_sidecars[{idx}] should be string")
        });
        assert!(
            path.ends_with(".raptorq.json"),
            "durability_evidence.raptorq_sidecars[{idx}] should end with .raptorq.json"
        );
        assert_path(
            path,
            &format!("durability_evidence.raptorq_sidecars[{idx}]"),
            &root,
        );
    }

    let decode_proofs = durability["decode_proofs"]
        .as_array()
        .expect("durability_evidence.decode_proofs should be array");
    assert!(
        !decode_proofs.is_empty(),
        "durability_evidence.decode_proofs should be non-empty"
    );
    for (idx, entry) in decode_proofs.iter().enumerate() {
        let path = entry
            .as_str()
            .unwrap_or_else(|| panic!("durability_evidence.decode_proofs[{idx}] should be string"));
        assert!(
            path.contains("decode_proof"),
            "durability_evidence.decode_proofs[{idx}] should reference decode proof artifacts"
        );
        assert_path(
            path,
            &format!("durability_evidence.decode_proofs[{idx}]"),
            &root,
        );
    }

    let scrub_reports = durability["integrity_scrub_reports"]
        .as_array()
        .expect("durability_evidence.integrity_scrub_reports should be array");
    assert!(
        !scrub_reports.is_empty(),
        "durability_evidence.integrity_scrub_reports should be non-empty"
    );
    for (idx, entry) in scrub_reports.iter().enumerate() {
        let path = entry.as_str().unwrap_or_else(|| {
            panic!("durability_evidence.integrity_scrub_reports[{idx}] should be string")
        });
        assert!(
            path.contains("durability_pipeline_report"),
            "durability_evidence.integrity_scrub_reports[{idx}] should reference durability pipeline report"
        );
        assert_path(
            path,
            &format!("durability_evidence.integrity_scrub_reports[{idx}]"),
            &root,
        );
    }

    let required_risk_keys = required_string_array(&schema, "required_risk_keys");
    let allowed_risk_severity = required_string_array(&schema, "allowed_risk_severity")
        .into_iter()
        .collect::<BTreeSet<_>>();
    let allowed_risk_status = required_string_array(&schema, "allowed_risk_status")
        .into_iter()
        .collect::<BTreeSet<_>>();
    let residual_risks = artifact["residual_risk_register"]
        .as_array()
        .expect("residual_risk_register should be array");
    assert!(
        !residual_risks.is_empty(),
        "residual_risk_register should be non-empty"
    );
    for (idx, risk) in residual_risks.iter().enumerate() {
        for key in &required_risk_keys {
            assert!(
                risk.get(*key).is_some(),
                "residual_risk_register[{idx}] missing key `{key}`"
            );
        }

        let severity = risk["severity"]
            .as_str()
            .expect("residual_risk_register severity should be string");
        assert!(
            allowed_risk_severity.contains(severity),
            "residual_risk_register[{idx}] severity `{severity}` outside allowed set"
        );

        let status = risk["status"]
            .as_str()
            .expect("residual_risk_register status should be string");
        assert!(
            allowed_risk_status.contains(status),
            "residual_risk_register[{idx}] status `{status}` outside allowed set"
        );

        let evidence_refs = risk["evidence_refs"]
            .as_array()
            .expect("residual_risk_register evidence_refs should be array");
        assert!(
            !evidence_refs.is_empty(),
            "residual_risk_register[{idx}] evidence_refs should be non-empty"
        );
        for (ref_idx, entry) in evidence_refs.iter().enumerate() {
            let path = entry.as_str().unwrap_or_else(|| {
                panic!("residual_risk_register[{idx}].evidence_refs[{ref_idx}] should be string")
            });
            assert_path(
                path,
                &format!("residual_risk_register[{idx}].evidence_refs[{ref_idx}]"),
                &root,
            );
        }
    }

    let required_review_cadence_keys =
        required_string_array(&schema, "required_review_cadence_keys");
    let review_cadence = artifact["review_cadence"]
        .as_array()
        .expect("review_cadence should be array");
    assert!(
        !review_cadence.is_empty(),
        "review_cadence should be non-empty"
    );
    for (idx, row) in review_cadence.iter().enumerate() {
        for key in &required_review_cadence_keys {
            assert!(
                row.get(*key).is_some(),
                "review_cadence[{idx}] missing key `{key}`"
            );
        }

        let required_inputs = row["required_inputs"]
            .as_array()
            .expect("review_cadence.required_inputs should be array");
        assert!(
            !required_inputs.is_empty(),
            "review_cadence[{idx}].required_inputs should be non-empty"
        );
        for (input_idx, entry) in required_inputs.iter().enumerate() {
            let path = entry.as_str().unwrap_or_else(|| {
                panic!("review_cadence[{idx}].required_inputs[{input_idx}] should be string")
            });
            assert_path(
                path,
                &format!("review_cadence[{idx}].required_inputs[{input_idx}]"),
                &root,
            );
        }

        let exit_criteria = row["exit_criteria"]
            .as_str()
            .expect("review_cadence.exit_criteria should be string");
        assert!(
            !exit_criteria.trim().is_empty(),
            "review_cadence[{idx}].exit_criteria should be non-empty"
        );
    }

    let required_audit_checklist_keys =
        required_string_array(&schema, "required_audit_checklist_keys");
    let required_audit_requirements = required_string_array(&schema, "required_audit_requirements")
        .into_iter()
        .collect::<BTreeSet<_>>();
    let checklist = artifact["audit_checklist"]
        .as_array()
        .expect("audit_checklist should be array");
    assert!(!checklist.is_empty(), "audit_checklist should be non-empty");

    let mut seen_requirements = BTreeSet::new();
    for (idx, row) in checklist.iter().enumerate() {
        for key in &required_audit_checklist_keys {
            assert!(
                row.get(*key).is_some(),
                "audit_checklist[{idx}] missing key `{key}`"
            );
        }

        let requirement = row["requirement"]
            .as_str()
            .expect("audit_checklist requirement should be string");
        assert!(
            required_audit_requirements.contains(requirement),
            "audit_checklist[{idx}] requirement `{requirement}` outside required set"
        );
        assert!(
            seen_requirements.insert(requirement),
            "duplicate requirement in audit_checklist: {requirement}"
        );

        let status = row["status"]
            .as_str()
            .expect("audit_checklist status should be string");
        assert_eq!(status, "pass", "audit_checklist[{idx}] status must be pass");

        let evidence_refs = row["evidence_refs"]
            .as_array()
            .expect("audit_checklist evidence_refs should be array");
        assert!(
            !evidence_refs.is_empty(),
            "audit_checklist[{idx}].evidence_refs should be non-empty"
        );
        for (ref_idx, entry) in evidence_refs.iter().enumerate() {
            let path = entry.as_str().unwrap_or_else(|| {
                panic!("audit_checklist[{idx}].evidence_refs[{ref_idx}] should be string")
            });
            assert_path(
                path,
                &format!("audit_checklist[{idx}].evidence_refs[{ref_idx}]"),
                &root,
            );
        }
    }
    assert_eq!(
        seen_requirements, required_audit_requirements,
        "audit_checklist should cover all required requirements exactly once"
    );

    let signoff = artifact["reviewer_signoff_package"]
        .as_object()
        .expect("reviewer_signoff_package should be object");
    for key in required_string_array(&schema, "required_signoff_keys") {
        assert!(
            signoff.get(key).is_some(),
            "reviewer_signoff_package missing key `{key}`"
        );
    }

    assert!(
        signoff["signoff_ready"]
            .as_bool()
            .expect("reviewer_signoff_package.signoff_ready should be bool"),
        "reviewer_signoff_package.signoff_ready should be true"
    );

    let reviewers = signoff["reviewers"]
        .as_array()
        .expect("reviewer_signoff_package.reviewers should be array");
    assert!(
        !reviewers.is_empty(),
        "reviewer_signoff_package.reviewers should be non-empty"
    );
    for (idx, entry) in reviewers.iter().enumerate() {
        let reviewer = entry.as_str().unwrap_or_else(|| {
            panic!("reviewer_signoff_package.reviewers[{idx}] should be string")
        });
        assert!(
            !reviewer.trim().is_empty(),
            "reviewer_signoff_package.reviewers[{idx}] should be non-empty"
        );
    }

    let replay_commands = signoff["independent_replay_commands"]
        .as_array()
        .expect("reviewer_signoff_package.independent_replay_commands should be array");
    assert!(
        !replay_commands.is_empty(),
        "reviewer_signoff_package.independent_replay_commands should be non-empty"
    );
    for (idx, entry) in replay_commands.iter().enumerate() {
        let command = entry.as_str().unwrap_or_else(|| {
            panic!("reviewer_signoff_package.independent_replay_commands[{idx}] should be string")
        });
        assert!(
            command.contains("rch exec --"),
            "reviewer_signoff_package.independent_replay_commands[{idx}] should use rch offload"
        );
    }

    let review_steps = signoff["review_steps"]
        .as_array()
        .expect("reviewer_signoff_package.review_steps should be array");
    assert!(
        review_steps.len() >= 3,
        "reviewer_signoff_package.review_steps should include at least three steps"
    );
    for (idx, entry) in review_steps.iter().enumerate() {
        let step = entry.as_str().unwrap_or_else(|| {
            panic!("reviewer_signoff_package.review_steps[{idx}] should be string")
        });
        assert!(
            !step.trim().is_empty(),
            "reviewer_signoff_package.review_steps[{idx}] should be non-empty"
        );
    }

    let traceability_refs = signoff["traceability_refs"]
        .as_array()
        .expect("reviewer_signoff_package.traceability_refs should be array");
    assert!(
        !traceability_refs.is_empty(),
        "reviewer_signoff_package.traceability_refs should be non-empty"
    );
    let mut traceability_set = BTreeSet::new();
    for (idx, entry) in traceability_refs.iter().enumerate() {
        let path = entry.as_str().unwrap_or_else(|| {
            panic!("reviewer_signoff_package.traceability_refs[{idx}] should be string")
        });
        traceability_set.insert(path.to_owned());
        assert_path(
            path,
            &format!("reviewer_signoff_package.traceability_refs[{idx}]"),
            &root,
        );
    }
    assert!(
        traceability_set.contains(artifact_path),
        "reviewer_signoff_package.traceability_refs should include attestation artifact path"
    );
    assert!(
        traceability_set.contains(schema_path),
        "reviewer_signoff_package.traceability_refs should include attestation schema path"
    );

    assert_eq!(
        validation["artifact"]
            .as_str()
            .expect("validation.artifact should be string"),
        artifact_path,
        "validation.artifact should point to attestation artifact path"
    );
    assert_eq!(
        validation["schema"]
            .as_str()
            .expect("validation.schema should be string"),
        schema_path,
        "validation.schema should point to attestation schema path"
    );
    assert!(
        validation["ready"]
            .as_bool()
            .expect("validation.ready should be bool"),
        "validation.ready should be true"
    );
    assert_eq!(
        validation["error_count"]
            .as_u64()
            .expect("validation.error_count should be u64"),
        0,
        "validation.error_count should be zero"
    );
    assert!(
        validation["errors"]
            .as_array()
            .expect("validation.errors should be array")
            .is_empty(),
        "validation.errors should be empty"
    );
}
