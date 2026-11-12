#![no_main]

use libfuzzer_sys::fuzz_target;
use std::fmt::Write;

fn parse_all(input: &str) {
    // Strict mode: must return Err on corruption, Ok on valid input.
    // For successful parses, assert the fundamental I/O-parser
    // invariant: every emitted edge's endpoints are members of the
    // parsed graph's node set.
    let mut strict = fnx_readwrite::EdgeListEngine::strict();
    if let Ok(report) = strict.read_gml(input) {
        for edge in report.graph.edges_ordered() {
            assert!(
                report.graph.has_node(&edge.left),
                "gml (strict): edge endpoint {} not in node set",
                edge.left
            );
            assert!(
                report.graph.has_node(&edge.right),
                "gml (strict): edge endpoint {} not in node set",
                edge.right
            );
        }
    }

    // Hardened mode: must return Ok with warnings or Ok empty, never panic.
    let mut hardened = fnx_readwrite::EdgeListEngine::hardened();
    if let Ok(report) = hardened.read_gml(input) {
        for edge in report.graph.edges_ordered() {
            assert!(
                report.graph.has_node(&edge.left),
                "gml (hardened): edge endpoint {} not in node set",
                edge.left
            );
            assert!(
                report.graph.has_node(&edge.right),
                "gml (hardened): edge endpoint {} not in node set",
                edge.right
            );
        }
    }

    // DiGraph variants.
    let mut strict_di = fnx_readwrite::EdgeListEngine::strict();
    if let Ok(report) = strict_di.read_digraph_gml(input) {
        for edge in report.graph.edges_ordered() {
            assert!(
                report.graph.has_node(&edge.left),
                "gml digraph (strict): edge endpoint {} not in node set",
                edge.left
            );
            assert!(
                report.graph.has_node(&edge.right),
                "gml digraph (strict): edge endpoint {} not in node set",
                edge.right
            );
        }
    }

    let mut hardened_di = fnx_readwrite::EdgeListEngine::hardened();
    if let Ok(report) = hardened_di.read_digraph_gml(input) {
        for edge in report.graph.edges_ordered() {
            assert!(
                report.graph.has_node(&edge.left),
                "gml digraph (hardened): edge endpoint {} not in node set",
                edge.left
            );
            assert!(
                report.graph.has_node(&edge.right),
                "gml digraph (hardened): edge endpoint {} not in node set",
                edge.right
            );
        }
    }

    // Directed detection helper — keep panic-only since the boolean
    // result is well-defined for malformed input.
    let mut detect = fnx_readwrite::EdgeListEngine::strict();
    let _ = detect.gml_declares_directed(input);
}

fn sanitized_token(data: &[u8], fallback: &str) -> String {
    let mut token = String::new();
    for byte in data.iter().copied().take(16) {
        let ch = byte as char;
        if ch.is_ascii_alphanumeric() || matches!(ch, '_' | '-' | '.') {
            token.push(ch);
        }
    }
    if token.is_empty() {
        fallback.to_owned()
    } else {
        token
    }
}

fn scalar_value(selector: u8) -> &'static str {
    match selector % 8 {
        0 => "0",
        1 => "1",
        2 => "-1",
        3 => "3.14159",
        4 => "\"quoted value\"",
        5 => "\"escaped &amp; value\"",
        6 => "NAN",
        _ => "unterminated",
    }
}

fn synthesize_gml(data: &[u8]) -> String {
    let selector = data.first().copied().unwrap_or(0);
    let node_count = usize::from(selector % 8);
    let edge_budget = usize::from(data.get(1).copied().unwrap_or(0) % 12);
    let directed_value = match data.get(2).copied().unwrap_or(0) % 5 {
        0 => Some("0"),
        1 => Some("1"),
        2 => Some("true"),
        3 => Some("2"),
        _ => None,
    };

    let mut input = String::new();
    let _ = writeln!(input, "# synthesized by fuzz_gml");
    if data.get(3).copied().unwrap_or(0) % 7 == 0 {
        let _ = writeln!(input, "preamble [ ignored 1 ]");
    }
    let _ = writeln!(input, "graph [");
    if let Some(value) = directed_value {
        let _ = writeln!(input, "  directed {value}");
    }
    let _ = writeln!(
        input,
        "  graph_attr {}",
        scalar_value(data.get(4).copied().unwrap_or(0)),
    );

    for idx in 0..node_count {
        let start = 5 + idx * 3;
        let end = data.len().min(start + 3);
        let label = sanitized_token(data.get(start..end).unwrap_or_default(), "node");
        match data.get(start).copied().unwrap_or(0) % 5 {
            0 => {
                let _ = writeln!(input, "  node [ id {idx} label \"{label}\" color \"red\" ]");
            }
            1 => {
                let _ = writeln!(input, "  node [ id {idx} label \"{label}\"");
            }
            2 => {
                let _ = writeln!(input, "  node [ id bad label \"{label}\" ]");
            }
            3 => {
                let _ = writeln!(input, "  node [ label \"{label}\" ]");
            }
            _ => {
                let _ = writeln!(
                    input,
                    "  node [ id {idx} value {} ]",
                    scalar_value(selector)
                );
            }
        }
    }

    for edge_idx in 0..edge_budget {
        let source = if node_count == 0 {
            0
        } else {
            usize::from(data.get(8 + edge_idx * 3).copied().unwrap_or(0)) % node_count
        };
        let target = if node_count == 0 {
            0
        } else {
            usize::from(data.get(9 + edge_idx * 3).copied().unwrap_or(0)) % node_count
        };
        match data.get(10 + edge_idx * 3).copied().unwrap_or(0) % 6 {
            0 => {
                let _ = writeln!(input, "  edge [ source {source} target {target} ]");
            }
            1 => {
                let _ = writeln!(
                    input,
                    "  edge [ source {source} target {target} weight {} ]",
                    scalar_value(edge_idx as u8),
                );
            }
            2 => {
                let _ = writeln!(input, "  edge [ source bad target {target} ]");
            }
            3 => {
                let _ = writeln!(input, "  edge [ source {source} ]");
            }
            4 => {
                let _ = writeln!(
                    input,
                    "  edge [ source {source} target {} ]",
                    node_count + 3
                );
            }
            _ => {
                let _ = writeln!(input, "  edge [ source {source} target {target}");
            }
        }
    }

    if data.get(5).copied().unwrap_or(0) % 11 != 0 {
        let _ = writeln!(input, "]");
    }
    input
}

fuzz_target!(|data: &[u8]| {
    if let Ok(input) = std::str::from_utf8(data) {
        parse_all(input);
    }

    let synthesized = synthesize_gml(data);
    parse_all(&synthesized);
});
