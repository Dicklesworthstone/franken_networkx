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

fn heading_paths(path: &Path) -> Vec<(String, usize)> {
    let raw = fs::read_to_string(path)
        .unwrap_or_else(|err| panic!("expected readable markdown at {}: {err}", path.display()));
    let mut stack: Vec<(usize, String)> = Vec::new();
    let mut out = Vec::new();
    for (idx, line) in raw.lines().enumerate() {
        let trimmed = line.trim_end();
        if !trimmed.starts_with('#') {
            continue;
        }
        let hashes = trimmed.chars().take_while(|ch| *ch == '#').count();
        if hashes == 0 || hashes > 6 {
            continue;
        }
        let title = trimmed[hashes..].trim();
        if title.is_empty() {
            continue;
        }
        while stack.last().is_some_and(|(level, _)| *level >= hashes) {
            stack.pop();
        }
        stack.push((hashes, title.to_owned()));
        let path_text = stack
            .iter()
            .map(|(_, part)| part.as_str())
            .collect::<Vec<_>>()
            .join(" > ");
        out.push((path_text, idx + 1));
    }
    out
}

#[test]
fn doc_pass00_gap_matrix_covers_all_headings_and_has_quant_targets() {
    let root = repo_root();
    let matrix = load_json(&root.join("artifacts/docs/v1/doc_pass00_gap_matrix_v1.json"));
    let sections = matrix["sections"]
        .as_array()
        .expect("sections should be an array");
    assert!(
        !sections.is_empty(),
        "doc pass gap matrix should include at least one section"
    );

    let expected_docs = [
        "EXHAUSTIVE_LEGACY_ANALYSIS.md",
        "EXISTING_NETWORKX_STRUCTURE.md",
    ];

    for doc in expected_docs {
        let headings = heading_paths(&root.join(doc));
        let expected = headings.into_iter().collect::<BTreeSet<_>>();
        let observed = sections
            .iter()
            .filter_map(|row| {
                if row["doc_path"].as_str() != Some(doc) {
                    return None;
                }
                Some((
                    row["heading_path"]
                        .as_str()
                        .expect("heading_path should be string")
                        .to_owned(),
                    row["start_line"]
                        .as_u64()
                        .expect("start_line should be integer") as usize,
                ))
            })
            .collect::<BTreeSet<_>>();
        assert_eq!(
            expected, observed,
            "doc gap matrix mapping drifted for {doc}"
        );
    }

    let mut observed_ranks = BTreeSet::new();
    for row in sections {
        let current_words = row["current_word_count"]
            .as_u64()
            .expect("current_word_count should be integer");
        let target_words = row["target_min_words"]
            .as_u64()
            .expect("target_min_words should be integer");
        let multiplier = row["expansion_multiplier"]
            .as_f64()
            .expect("expansion_multiplier should be numeric");
        let coverage = row["coverage_ratio"]
            .as_f64()
            .expect("coverage_ratio should be numeric");
        let risk = row["risk_tier"]
            .as_str()
            .expect("risk_tier should be string");
        let missing_topics = row["missing_topics"]
            .as_array()
            .expect("missing_topics should be array");
        let rank = row["priority_rank"]
            .as_u64()
            .expect("priority_rank should be integer");

        assert!(
            matches!(risk, "high" | "medium" | "low"),
            "invalid risk tier {risk}"
        );
        assert!(
            (0.0..=1.0).contains(&coverage),
            "coverage_ratio must be between 0 and 1"
        );
        assert!(multiplier >= 1.5, "expansion_multiplier must be >= 1.5");
        assert!(
            target_words >= current_words,
            "target words must be >= current words"
        );
        assert!(
            missing_topics.iter().all(|topic| topic.is_string()),
            "missing_topics entries must be strings"
        );
        observed_ranks.insert(rank);
    }

    let expected_ranks = (1..=sections.len() as u64).collect::<BTreeSet<_>>();
    assert_eq!(
        observed_ranks, expected_ranks,
        "priority_rank should be contiguous 1..N"
    );

    let ev_score = matrix["alien_uplift_contract_card"]["ev_score"]
        .as_f64()
        .expect("ev_score should be numeric");
    assert!(ev_score >= 2.0, "ev_score must be >= 2.0");
}
