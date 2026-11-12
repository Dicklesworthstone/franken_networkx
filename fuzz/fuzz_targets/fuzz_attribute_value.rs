#![no_main]

use fnx_readwrite::EdgeListEngine;
use fnx_runtime::CgseValue;
use libfuzzer_sys::fuzz_target;

fn sanitized_key(data: &[u8]) -> String {
    let mut out = String::new();
    for byte in data.iter().copied().take(16) {
        let ch = byte as char;
        if ch.is_ascii_alphanumeric() || ch == '_' {
            out.push(ch.to_ascii_lowercase());
        }
    }
    if out.is_empty() {
        "attr".to_owned()
    } else {
        out
    }
}

fn text_fragment(data: &[u8]) -> String {
    String::from_utf8_lossy(data).chars().take(64).collect()
}

fn compact_token(raw: &str) -> String {
    let mut out = String::new();
    for ch in raw.chars().take(32) {
        if ch.is_ascii_alphanumeric() || matches!(ch, '.' | '-' | '_') {
            out.push(ch);
        } else if !out.ends_with('_') {
            out.push('_');
        }
    }
    if out.is_empty() {
        "value".to_owned()
    } else {
        out
    }
}

fn json_escape(raw: &str) -> String {
    let mut out = String::new();
    for ch in raw.chars() {
        match ch {
            '\\' => out.push_str("\\\\"),
            '"' => out.push_str("\\\""),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            ch if ch.is_control() => {
                let _ = std::fmt::Write::write_fmt(&mut out, format_args!("\\u{:04x}", ch as u32));
            }
            _ => out.push(ch),
        }
    }
    out
}

fn xml_escape(raw: &str) -> String {
    raw.replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
}

fn gml_escape(raw: &str) -> String {
    raw.replace('\\', "\\\\").replace('"', "\\\"")
}

fn graphml_attr_type(selector: u8) -> &'static str {
    match selector % 5 {
        0 => "string",
        1 => "boolean",
        2 => "int",
        3 => "double",
        _ => "mystery",
    }
}

fn json_literal(raw: &str, selector: u8) -> String {
    match selector % 5 {
        0 => format!("\"{}\"", json_escape(raw)),
        1 => raw
            .trim()
            .parse::<i64>()
            .map_or_else(|_| "0".to_owned(), |value| value.to_string()),
        2 => raw.trim().parse::<f64>().map_or_else(
            |_| "0.0".to_owned(),
            |value| {
                if value.is_finite() {
                    value.to_string()
                } else {
                    "0.0".to_owned()
                }
            },
        ),
        3 => {
            if raw.len().is_multiple_of(2) {
                "true".to_owned()
            } else {
                "false".to_owned()
            }
        }
        _ => "null".to_owned(),
    }
}

fn gml_literal(raw: &str, selector: u8) -> String {
    match selector % 4 {
        0 => format!("\"{}\"", gml_escape(raw)),
        1 => compact_token(raw)
            .parse::<i64>()
            .map_or_else(|_| "0".to_owned(), |value| value.to_string()),
        2 => {
            if raw.eq_ignore_ascii_case("true") {
                "1".to_owned()
            } else {
                "0".to_owned()
            }
        }
        _ => format!("\"{}\"", gml_escape(raw)),
    }
}

fuzz_target!(|data: &[u8]| {
    if data.is_empty() {
        return;
    }

    let raw = text_fragment(data);
    let key = sanitized_key(data);
    let edgelist_value = compact_token(&raw);

    let _ = CgseValue::parse_relaxed(&raw);

    let edgelist = format!("a b {key}={edgelist_value}");
    let mut edgelist_strict = EdgeListEngine::strict();
    if let Ok(report) = edgelist_strict.read_edgelist(&edgelist) {
        // Synthesized payload has 2 nodes + 1 edge.
        assert!(report.graph.node_count() <= 2,
            "edgelist parse produced {} nodes (expected ≤ 2)",
            report.graph.node_count());
        assert!(report.graph.edge_count() <= 1,
            "edgelist parse produced {} edges (expected ≤ 1)",
            report.graph.edge_count());
    }
    let mut edgelist_hardened = EdgeListEngine::hardened();
    if let Ok(report) = edgelist_hardened.read_edgelist(&edgelist) {
        assert!(report.graph.node_count() <= 2,
            "edgelist (hardened) parse produced {} nodes",
            report.graph.node_count());
        assert!(report.graph.edge_count() <= 1,
            "edgelist (hardened) parse produced {} edges",
            report.graph.edge_count());
    }

    let graphml = format!(
        concat!(
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>",
            "<graphml xmlns=\"http://graphml.graphdrawing.org/xmlns\">",
            "<key id=\"d0\" for=\"edge\" attr.name=\"{key}\" attr.type=\"{attr_type}\"/>",
            "<graph id=\"G\" edgedefault=\"undirected\">",
            "<node id=\"a\"/><node id=\"b\"/>",
            "<edge source=\"a\" target=\"b\"><data key=\"d0\">{value}</data></edge>",
            "</graph></graphml>"
        ),
        key = key,
        attr_type = graphml_attr_type(data.first().copied().unwrap_or(0)),
        value = xml_escape(&raw),
    );
    let mut graphml_strict = EdgeListEngine::strict();
    if let Ok(report) = graphml_strict.read_graphml(&graphml) {
        assert!(report.graph.node_count() <= 2,
            "graphml parse produced {} nodes (expected ≤ 2)",
            report.graph.node_count());
        assert!(report.graph.edge_count() <= 1,
            "graphml parse produced {} edges (expected ≤ 1)",
            report.graph.edge_count());
    }
    let mut graphml_hardened = EdgeListEngine::hardened();
    if let Ok(report) = graphml_hardened.read_graphml(&graphml) {
        assert!(report.graph.node_count() <= 2,
            "graphml (hardened) parse produced {} nodes",
            report.graph.node_count());
        assert!(report.graph.edge_count() <= 1,
            "graphml (hardened) parse produced {} edges",
            report.graph.edge_count());
    }

    let gml = format!(
        concat!(
            "graph [ directed 0 ",
            "node [ id 0 label \"a\" ] ",
            "node [ id 1 label \"b\" ] ",
            "edge [ source 0 target 1 {key} {value} ] ]"
        ),
        key = key,
        value = gml_literal(&raw, data.get(1).copied().unwrap_or(0)),
    );
    let mut gml_strict = EdgeListEngine::strict();
    if let Ok(report) = gml_strict.read_gml(&gml) {
        assert!(report.graph.node_count() <= 2,
            "gml parse produced {} nodes (expected ≤ 2)",
            report.graph.node_count());
        assert!(report.graph.edge_count() <= 1,
            "gml parse produced {} edges (expected ≤ 1)",
            report.graph.edge_count());
    }
    let mut gml_hardened = EdgeListEngine::hardened();
    if let Ok(report) = gml_hardened.read_gml(&gml) {
        assert!(report.graph.node_count() <= 2,
            "gml (hardened) parse produced {} nodes",
            report.graph.node_count());
        assert!(report.graph.edge_count() <= 1,
            "gml (hardened) parse produced {} edges",
            report.graph.edge_count());
    }

    let attr_json = format!(
        "{{\"{key}\":{value}}}",
        key = key,
        value = json_literal(&raw, data.get(2).copied().unwrap_or(0)),
    );
    let json_payload = format!(
        concat!(
            "{{",
            "\"mode\":\"strict\",",
            "\"directed\":false,",
            "\"graph_attrs\":{{}},",
            "\"nodes\":[\"a\",\"b\"],",
            "\"edges\":[{{\"left\":\"a\",\"right\":\"b\",\"attrs\":{attrs}}}]",
            "}}"
        ),
        attrs = attr_json,
    );
    let mut json_strict = EdgeListEngine::strict();
    if let Ok(report) = json_strict.read_json_graph(&json_payload) {
        assert!(report.graph.node_count() <= 2,
            "json parse produced {} nodes (expected ≤ 2)",
            report.graph.node_count());
        assert!(report.graph.edge_count() <= 1,
            "json parse produced {} edges (expected ≤ 1)",
            report.graph.edge_count());
    }
    let mut json_hardened = EdgeListEngine::hardened();
    if let Ok(report) = json_hardened.read_json_graph(&json_payload) {
        assert!(report.graph.node_count() <= 2,
            "json (hardened) parse produced {} nodes",
            report.graph.node_count());
        assert!(report.graph.edge_count() <= 1,
            "json (hardened) parse produced {} edges",
            report.graph.edge_count());
    }
});
