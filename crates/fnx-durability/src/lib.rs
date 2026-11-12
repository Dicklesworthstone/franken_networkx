#![forbid(unsafe_code)]

use base64::Engine;
use base64::engine::general_purpose::STANDARD;
use raptorq::{Decoder, Encoder, EncodingPacket, ObjectTransmissionInformation, partition};
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};
use std::fmt;
use std::fs;
use std::io::{Read, Write};
use std::path::Path;
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use thiserror::Error;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ScrubState {
    Ok,
    Recovered,
    Failed,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ScrubStatus {
    pub last_ok_unix_ms: u128,
    pub status: ScrubState,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct DecodeProof {
    pub ts_unix_ms: u128,
    pub reason: String,
    pub recovered_blocks: u32,
    pub proof_hash: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub dropped_packets: Option<u32>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub fail_closed_beyond: Option<u32>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub dropped_source_packets: Option<Vec<SourcePacketLoss>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub loss_selection: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SourcePacketLoss {
    pub source_block: u8,
    pub encoding_symbol_id: u32,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct RaptorQSidecar {
    pub k: u32,
    pub repair_symbols: u32,
    pub overhead_ratio: f64,
    pub symbol_hashes: Vec<String>,
    pub oti_b64: String,
    pub packets_b64: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ArtifactEnvelope {
    pub artifact_id: String,
    pub artifact_type: String,
    pub source_hash: String,
    pub raptorq: RaptorQSidecar,
    pub scrub: ScrubStatus,
    pub decode_proofs: Vec<DecodeProof>,
}

#[derive(Debug, Error)]
pub enum DurabilityError {
    #[error("io error: {0}")]
    Io(#[from] std::io::Error),
    #[error("json error: {0}")]
    Json(#[from] serde_json::Error),
    #[error("base64 error: {0}")]
    Base64(#[from] base64::DecodeError),
    #[error("invalid object transmission information length")]
    InvalidOtiLength,
    #[error("encoding MTU must be nonzero")]
    InvalidMtu,
    #[error("payload and MTU exceed RaptorQ source-block limits")]
    InvalidEncodingParameters,
    #[error("decode failed: insufficient or invalid packets")]
    DecodeFailed,
    #[error("decoded payload hash mismatch with source hash")]
    HashMismatch,
    #[error(
        "decode drill packet layout mismatch: expected {expected_sources} source and {expected_repairs} repair packets, observed {observed_sources} source and {observed_repairs} repair"
    )]
    DecodeDrillPacketLayout {
        expected_sources: u32,
        expected_repairs: u32,
        observed_sources: u32,
        observed_repairs: u32,
    },
    #[error("decode drill did not fail closed beyond the validated loss bound")]
    DecodeDrillFailOpen,
    #[error("source-loss decode drill requires repair packets for a nonempty payload")]
    DecodeDrillNoRepairPackets,
    #[error("invalid release evidence: {0}")]
    InvalidReleaseEvidence(String),
}

pub const MAX_DURABILITY_FILE_SIZE: usize = 100 * 1024 * 1024; // 100MB
pub const RELEASE_EVIDENCE_CLASSES: [&str; 5] = [
    "conformance_fixtures",
    "benchmark_baselines",
    "migration_manifests",
    "reproducibility_ledgers",
    "long_lived_snapshots",
];

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ReleaseEvidenceMember {
    pub class: String,
    pub path: String,
    pub source_hash: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ReleaseEvidenceManifest {
    pub schema: String,
    pub members: Vec<ReleaseEvidenceMember>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ReleaseEvidenceRecord {
    pub member: ReleaseEvidenceMember,
    pub bytes: u64,
    pub sidecar_hash: String,
    pub scrub_report_hash: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ReleaseEvidenceBundle {
    pub schema: String,
    pub candidate_id: String,
    pub input_manifest_hash: String,
    pub members: Vec<ReleaseEvidenceRecord>,
}

pub fn generate_sidecar_for_file(
    artifact_path: &Path,
    sidecar_path: &Path,
    artifact_id: &str,
    artifact_type: &str,
    mtu: u16,
    repair_symbols: u32,
) -> Result<ArtifactEnvelope, DurabilityError> {
    if mtu == 0 {
        return Err(DurabilityError::InvalidMtu);
    }
    let metadata = fs::metadata(artifact_path)?;
    if metadata.len() > MAX_DURABILITY_FILE_SIZE as u64 {
        return Err(DurabilityError::Io(std::io::Error::new(
            std::io::ErrorKind::FileTooLarge,
            format!(
                "file size {} exceeds maximum allowed {} bytes",
                metadata.len(),
                MAX_DURABILITY_FILE_SIZE
            ),
        )));
    }

    let data = fs::read(artifact_path)?;
    let source_hash = hash_bytes(&data);

    if data.is_empty() {
        let envelope = ArtifactEnvelope {
            artifact_id: artifact_id.to_owned(),
            artifact_type: artifact_type.to_owned(),
            source_hash,
            raptorq: RaptorQSidecar {
                k: 0,
                repair_symbols: 0,
                overhead_ratio: 0.0,
                symbol_hashes: Vec::new(),
                oti_b64: String::new(),
                packets_b64: Vec::new(),
            },
            scrub: ScrubStatus {
                last_ok_unix_ms: unix_time_ms(),
                status: ScrubState::Ok,
            },
            decode_proofs: Vec::new(),
        };
        write_envelope(sidecar_path, &envelope)?;
        return Ok(envelope);
    }

    // The default parameter builder narrows its source-block count to u8.
    // A small MTU can overflow it even within our 100MiB payload limit;
    // validate before constructing an encoder (which would otherwise panic).
    let config = validate_oti(ObjectTransmissionInformation::with_defaults(
        data.len() as u64,
        mtu,
    ))
    .map_err(|_| DurabilityError::InvalidEncodingParameters)?;
    let encoder = Encoder::new(&data, config);

    let total_k = source_packet_count_from_oti(&config);

    let blocks = encoder.get_block_encoders().len() as u32;
    let repair_per_block = if blocks == 0 {
        0
    } else {
        repair_symbols.div_ceil(blocks)
    };

    let packets = encoder.get_encoded_packets(repair_per_block);
    let actual_repair_count = packets.len() as u32 - total_k;

    let serialized_packets: Vec<Vec<u8>> = packets.iter().map(EncodingPacket::serialize).collect();
    let symbol_hashes: Vec<String> = serialized_packets
        .iter()
        .map(|bytes| hash_bytes(bytes))
        .collect();
    let packets_b64: Vec<String> = serialized_packets
        .iter()
        .map(|bytes| STANDARD.encode(bytes))
        .collect();
    let oti_b64 = STANDARD.encode(config.serialize());

    let overhead_ratio = if total_k == 0 {
        0.0
    } else {
        f64::from(actual_repair_count) / f64::from(total_k)
    };

    let envelope = ArtifactEnvelope {
        artifact_id: artifact_id.to_owned(),
        artifact_type: artifact_type.to_owned(),
        source_hash,
        raptorq: RaptorQSidecar {
            k: total_k,
            repair_symbols: actual_repair_count,
            overhead_ratio,
            symbol_hashes,
            oti_b64,
            packets_b64,
        },
        scrub: ScrubStatus {
            last_ok_unix_ms: unix_time_ms(),
            status: ScrubState::Ok,
        },
        decode_proofs: Vec::new(),
    };

    write_envelope(sidecar_path, &envelope)?;
    Ok(envelope)
}

pub fn scrub_artifact(
    artifact_path: &Path,
    sidecar_path: &Path,
) -> Result<ArtifactEnvelope, DurabilityError> {
    let mut envelope = read_envelope(sidecar_path)?;

    let current_source_hash = if artifact_path.exists() {
        hash_bytes(&fs::read(artifact_path)?)
    } else {
        String::new()
    };

    if current_source_hash == envelope.source_hash {
        envelope.scrub = ScrubStatus {
            last_ok_unix_ms: unix_time_ms(),
            status: ScrubState::Ok,
        };
        write_envelope(sidecar_path, &envelope)?;
        return Ok(envelope);
    }

    let recovered = decode_from_envelope(&envelope)?;
    let recovered_hash = hash_bytes(&recovered);
    if recovered_hash != envelope.source_hash {
        envelope.scrub.status = ScrubState::Failed;
        let _ = write_envelope(sidecar_path, &envelope);
        return Err(DurabilityError::HashMismatch);
    }

    fs::write(artifact_path, &recovered)?;
    let proof = DecodeProof {
        ts_unix_ms: unix_time_ms(),
        reason: "scrub_recovery".to_owned(),
        recovered_blocks: recovered_source_blocks(&envelope)?,
        proof_hash: recovered_hash.clone(),
        dropped_packets: None,
        fail_closed_beyond: None,
        dropped_source_packets: None,
        loss_selection: None,
    };
    envelope.decode_proofs.push(proof);
    envelope.scrub = ScrubStatus {
        last_ok_unix_ms: unix_time_ms(),
        status: ScrubState::Recovered,
    };
    write_envelope(sidecar_path, &envelope)?;
    Ok(envelope)
}

pub fn run_decode_drill(
    sidecar_path: &Path,
    recovered_output: &Path,
) -> Result<ArtifactEnvelope, DurabilityError> {
    let mut envelope = read_envelope(sidecar_path)?;
    let (source_packets, repair_packets) = classify_decode_drill_packets(&envelope)?;
    let (retained_packets, dropped_sources) =
        prepare_source_loss_drill(&envelope, &source_packets, &repair_packets)?;
    let recovered = decode_with_binary_packets(&envelope, retained_packets)?;
    // The negative is deliberately a DIFFERENT loss pattern: all repairs
    // plus one source are absent. A successful selected pattern is not a
    // claim that RaptorQ is MDS or tolerates every same-cardinality pattern.
    let fail_closed_beyond = verify_decode_drill_fail_closed(
        &envelope,
        &source_packets,
        envelope.raptorq.repair_symbols,
    )?;
    let reason = if envelope.raptorq.k == 0 {
        "decode_drill_empty"
    } else {
        "decode_drill_source_loss_success"
    };

    let recovered_hash = hash_bytes(&recovered);
    if recovered_hash != envelope.source_hash {
        return Err(DurabilityError::HashMismatch);
    }

    fs::write(recovered_output, &recovered)?;
    let proof = DecodeProof {
        ts_unix_ms: unix_time_ms(),
        reason: reason.to_owned(),
        recovered_blocks: recovered_source_blocks(&envelope)?,
        proof_hash: recovered_hash.clone(),
        dropped_packets: Some(
            u32::try_from(dropped_sources.len()).map_err(|_| DurabilityError::DecodeFailed)?,
        ),
        fail_closed_beyond,
        dropped_source_packets: Some(dropped_sources),
        loss_selection: Some("blake3-source-hash-packet-id-v1".to_owned()),
    };
    envelope.decode_proofs.push(proof);
    envelope.scrub = ScrubStatus {
        last_ok_unix_ms: unix_time_ms(),
        status: ScrubState::Recovered,
    };
    write_envelope(sidecar_path, &envelope)?;
    Ok(envelope)
}

fn invalid_evidence(message: &str) -> DurabilityError {
    DurabilityError::InvalidReleaseEvidence(message.to_owned())
}

fn validate_evidence_manifest(
    manifest: &ReleaseEvidenceManifest,
    expected_candidate: &str,
) -> Result<(), DurabilityError> {
    if manifest.schema != "fnx-release-evidence-input-v1"
        || expected_candidate.len() != 64
        || !expected_candidate
            .bytes()
            .all(|byte| byte.is_ascii_hexdigit())
        || manifest.members.is_empty()
        || manifest.members.len() > 10_000
    {
        return Err(invalid_evidence(
            "schema, candidate or member count mismatch",
        ));
    }
    let mut classes = BTreeSet::new();
    let mut paths = BTreeSet::new();
    for member in &manifest.members {
        if !RELEASE_EVIDENCE_CLASSES.contains(&member.class.as_str())
            || member.path.contains(['\\', ':'])
            || member.path.chars().any(char::is_control)
            || member
                .path
                .split('/')
                .any(|part| matches!(part, "" | "." | ".."))
            || !paths.insert(&member.path)
            || !member.source_hash.starts_with("blake3:")
            || member.source_hash.len() != 71
            || !member.source_hash[7..]
                .bytes()
                .all(|byte| byte.is_ascii_hexdigit())
        {
            return Err(invalid_evidence(
                "invalid class, path, duplicate or source hash",
            ));
        }
        classes.insert(member.class.as_str());
    }
    if classes != RELEASE_EVIDENCE_CLASSES.into_iter().collect() {
        return Err(invalid_evidence(
            "all five required evidence classes must be populated",
        ));
    }
    Ok(())
}

fn regular_bytes(path: &Path, limit: usize) -> Result<Vec<u8>, DurabilityError> {
    if !fs::symlink_metadata(path)?.file_type().is_file() {
        return Err(invalid_evidence(
            "evidence must be a regular non-symlink file",
        ));
    }
    let mut bytes = Vec::new();
    fs::File::open(path)?
        .take(limit as u64 + 1)
        .read_to_end(&mut bytes)?;
    if bytes.len() > limit {
        return Err(invalid_evidence("evidence exceeds the bounded file size"));
    }
    Ok(bytes)
}

fn evidence_source(
    root: &Path,
    member: &ReleaseEvidenceMember,
) -> Result<std::path::PathBuf, DurabilityError> {
    let mut path = root.to_path_buf();
    for component in member.path.split('/') {
        path.push(component);
        if fs::symlink_metadata(&path)?.file_type().is_symlink() {
            return Err(invalid_evidence("linked evidence paths are not admitted"));
        }
    }
    Ok(path)
}

fn regular_directory(path: &Path) -> Result<(), DurabilityError> {
    if !fs::symlink_metadata(path)?.file_type().is_dir() {
        return Err(invalid_evidence("bundle directories must not be links"));
    }
    Ok(())
}

fn write_new(path: &Path, data: &[u8]) -> Result<(), DurabilityError> {
    fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(path)?
        .write_all(data)?;
    Ok(())
}

/// Prepare actual, explicitly enumerated release payloads without modifying
/// their source files. Completion is published only after all five classes
/// pass byte-exact source-loss recovery and the independent over-budget drill.
pub fn prepare_release_evidence(
    payload_root: &Path,
    manifest_path: &Path,
    output_dir: &Path,
    expected_candidate: &str,
) -> Result<ReleaseEvidenceBundle, DurabilityError> {
    let raw_manifest = regular_bytes(manifest_path, MAX_DURABILITY_FILE_SIZE)?;
    let manifest: ReleaseEvidenceManifest = serde_json::from_slice(&raw_manifest)?;
    validate_evidence_manifest(&manifest, expected_candidate)?;
    let root = payload_root.canonicalize()?;
    for member in &manifest.members {
        evidence_source(&root, member)?;
    }
    // create_dir, not create_dir_all: an existing bundle is never overwritten.
    fs::create_dir(output_dir)?;
    let mut records = Vec::with_capacity(manifest.members.len());
    for (index, member) in manifest.members.iter().enumerate() {
        let source = evidence_source(&root, member)?;
        let bytes = regular_bytes(&source, MAX_DURABILITY_FILE_SIZE)?;
        if bytes.is_empty() || hash_bytes(&bytes) != member.source_hash {
            return Err(invalid_evidence("empty or stale source payload"));
        }
        let directory = output_dir.join(format!("{index:05}"));
        fs::create_dir(&directory)?;
        let payload = directory.join("payload.bin");
        let sidecar = directory.join("payload.raptorq.json");
        let recovered = directory.join("recovered.bin");
        write_new(&payload, &bytes)?;
        generate_sidecar_for_file(
            &payload,
            &sidecar,
            &format!("{expected_candidate}:{index}:{}", member.path),
            &member.class,
            1400,
            6,
        )?;
        let scrubbed = scrub_artifact(&payload, &sidecar)?;
        if scrubbed.scrub.status != ScrubState::Ok || scrubbed.source_hash != member.source_hash {
            return Err(invalid_evidence(
                "fresh payload scrub did not remain intact",
            ));
        }
        let scrub_report = serde_json::to_vec_pretty(&scrubbed)?;
        write_new(&directory.join("scrub.json"), &scrub_report)?;
        run_decode_drill(&sidecar, &recovered)?;
        if regular_bytes(&recovered, MAX_DURABILITY_FILE_SIZE)? != bytes
            || regular_bytes(&source, MAX_DURABILITY_FILE_SIZE)? != bytes
        {
            return Err(invalid_evidence("source moved or recovered bytes differ"));
        }
        records.push(ReleaseEvidenceRecord {
            member: member.clone(),
            bytes: bytes.len() as u64,
            sidecar_hash: hash_bytes(&regular_bytes(&sidecar, MAX_DURABILITY_FILE_SIZE * 4)?),
            scrub_report_hash: hash_bytes(&scrub_report),
        });
    }
    if regular_bytes(manifest_path, MAX_DURABILITY_FILE_SIZE)? != raw_manifest {
        return Err(invalid_evidence("input manifest moved during preparation"));
    }
    for record in &records {
        if hash_bytes(&regular_bytes(
            &evidence_source(&root, &record.member)?,
            MAX_DURABILITY_FILE_SIZE,
        )?) != record.member.source_hash
        {
            return Err(invalid_evidence("source moved before bundle completion"));
        }
    }
    let bundle = ReleaseEvidenceBundle {
        schema: "fnx-release-evidence-bundle-v1".to_owned(),
        candidate_id: expected_candidate.to_owned(),
        input_manifest_hash: hash_bytes(&raw_manifest),
        members: records,
    };
    write_new(&output_dir.join("input-manifest.json"), &raw_manifest)?;
    verify_release_payloads(
        output_dir,
        expected_candidate,
        &raw_manifest,
        &manifest,
        &bundle,
    )?;
    write_new(
        &output_dir.join("bundle.json"),
        &serde_json::to_vec_pretty(&bundle)?,
    )?;
    Ok(bundle)
}

/// Re-execute decoding from the sidecar's selected source-loss packet set.
/// No source file is required and no packaged file is modified by verification.
pub fn verify_release_evidence(
    bundle_dir: &Path,
    expected_candidate: &str,
) -> Result<ReleaseEvidenceBundle, DurabilityError> {
    regular_directory(bundle_dir)?;
    let input = regular_bytes(
        &bundle_dir.join("input-manifest.json"),
        MAX_DURABILITY_FILE_SIZE,
    )?;
    let manifest: ReleaseEvidenceManifest = serde_json::from_slice(&input)?;
    validate_evidence_manifest(&manifest, expected_candidate)?;
    let bundle: ReleaseEvidenceBundle = serde_json::from_slice(&regular_bytes(
        &bundle_dir.join("bundle.json"),
        MAX_DURABILITY_FILE_SIZE,
    )?)?;
    verify_release_payloads(bundle_dir, expected_candidate, &input, &manifest, &bundle)?;
    Ok(bundle)
}

fn verify_release_payloads(
    bundle_dir: &Path,
    expected_candidate: &str,
    input: &[u8],
    manifest: &ReleaseEvidenceManifest,
    bundle: &ReleaseEvidenceBundle,
) -> Result<(), DurabilityError> {
    if bundle.schema != "fnx-release-evidence-bundle-v1"
        || bundle.candidate_id != expected_candidate
        || bundle.input_manifest_hash != hash_bytes(input)
        || bundle.members.len() != manifest.members.len()
    {
        return Err(invalid_evidence(
            "bundle does not join the exact input manifest",
        ));
    }
    for (index, (record, member)) in bundle.members.iter().zip(&manifest.members).enumerate() {
        if record.member.class != member.class
            || record.member.path != member.path
            || record.member.source_hash != member.source_hash
        {
            return Err(invalid_evidence("bundle member set or ordering mismatch"));
        }
        let directory = bundle_dir.join(format!("{index:05}"));
        regular_directory(&directory)?;
        let payload = regular_bytes(&directory.join("payload.bin"), MAX_DURABILITY_FILE_SIZE)?;
        let recovered = regular_bytes(&directory.join("recovered.bin"), MAX_DURABILITY_FILE_SIZE)?;
        let sidecar = regular_bytes(
            &directory.join("payload.raptorq.json"),
            MAX_DURABILITY_FILE_SIZE * 4,
        )?;
        let scrub = regular_bytes(&directory.join("scrub.json"), MAX_DURABILITY_FILE_SIZE * 4)?;
        if payload.is_empty()
            || payload.len() as u64 != record.bytes
            || payload != recovered
            || hash_bytes(&payload) != member.source_hash
            || hash_bytes(&sidecar) != record.sidecar_hash
            || hash_bytes(&scrub) != record.scrub_report_hash
        {
            return Err(invalid_evidence("stale payload, recovery or sidecar"));
        }
        let envelope: ArtifactEnvelope = serde_json::from_slice(&sidecar)?;
        let scrub_report: ArtifactEnvelope = serde_json::from_slice(&scrub)?;
        if envelope.source_hash != member.source_hash
            || envelope.artifact_type != member.class
            || envelope.artifact_id != format!("{expected_candidate}:{index}:{}", member.path)
            || envelope.scrub.status != ScrubState::Recovered
            || scrub_report.artifact_id != envelope.artifact_id
            || scrub_report.artifact_type != envelope.artifact_type
            || scrub_report.source_hash != envelope.source_hash
            || scrub_report.raptorq != envelope.raptorq
            || scrub_report.scrub.status != ScrubState::Ok
            || !scrub_report.decode_proofs.is_empty()
        {
            return Err(invalid_evidence(
                "sidecar identity differs from its payload",
            ));
        }
        let (sources, repairs) = classify_decode_drill_packets(&envelope)?;
        let (retained, lost) = prepare_source_loss_drill(&envelope, &sources, &repairs)?;
        let proof = envelope
            .decode_proofs
            .last()
            .ok_or_else(|| invalid_evidence("missing source-loss proof"))?;
        if lost.is_empty()
            || proof.reason != "decode_drill_source_loss_success"
            || proof.proof_hash != member.source_hash
            || proof.recovered_blocks != recovered_source_blocks(&envelope)?
            || proof.dropped_source_packets.as_ref() != Some(&lost)
            || proof.dropped_packets != Some(lost.len() as u32)
            || proof.loss_selection.as_deref() != Some("blake3-source-hash-packet-id-v1")
            || proof.fail_closed_beyond
                != verify_decode_drill_fail_closed(
                    &envelope,
                    &sources,
                    envelope.raptorq.repair_symbols,
                )?
            || decode_with_binary_packets(&envelope, retained)? != payload
        {
            return Err(invalid_evidence(
                "recorded proof differs from live source-loss decoding",
            ));
        }
    }
    Ok(())
}

pub fn read_envelope(path: &Path) -> Result<ArtifactEnvelope, DurabilityError> {
    let raw = fs::read_to_string(path)?;
    Ok(serde_json::from_str(&raw)?)
}

pub fn write_envelope(path: &Path, envelope: &ArtifactEnvelope) -> Result<(), DurabilityError> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    let serialized = serde_json::to_string_pretty(envelope)?;
    let temp_path = path.with_extension("tmp.json");
    fs::write(&temp_path, serialized)?;
    fs::rename(&temp_path, path)?;
    Ok(())
}

fn decode_from_envelope(envelope: &ArtifactEnvelope) -> Result<Vec<u8>, DurabilityError> {
    // Scrub recovery admits packet erasures. The release drill separately
    // requires a complete initial inventory to account for its selected loss.
    decode_with_packets(envelope, &envelope.raptorq.packets_b64)
}

fn classify_decode_drill_packets(
    envelope: &ArtifactEnvelope,
) -> Result<(Vec<EncodingPacket>, Vec<EncodingPacket>), DurabilityError> {
    if envelope.raptorq.k == 0 {
        if envelope.raptorq.repair_symbols != 0
            || !envelope.raptorq.packets_b64.is_empty()
            || !envelope.raptorq.symbol_hashes.is_empty()
            || !envelope.raptorq.oti_b64.is_empty()
        {
            return Err(DurabilityError::DecodeFailed);
        }
        return Ok((Vec::new(), Vec::new()));
    }

    let oti = decode_oti(&envelope.raptorq.oti_b64)?;
    let total_source_packets =
        u32::try_from(oti.transfer_length().div_ceil(u64::from(oti.symbol_size())))
            .map_err(|_| DurabilityError::DecodeFailed)?;
    let (large_block_symbols, small_block_symbols, large_block_count, _) =
        partition(total_source_packets, u32::from(oti.source_blocks()));
    if total_source_packets != envelope.raptorq.k
        || envelope.raptorq.packets_b64.len() != envelope.raptorq.symbol_hashes.len()
        || envelope.raptorq.packets_b64.len() as u64
            != u64::from(envelope.raptorq.k) + u64::from(envelope.raptorq.repair_symbols)
    {
        return Err(DurabilityError::DecodeFailed);
    }

    let mut source_packets = Vec::with_capacity(envelope.raptorq.k as usize);
    let mut repair_packets = Vec::new();
    let mut seen = BTreeSet::new();

    for (encoded, expected_hash) in envelope
        .raptorq
        .packets_b64
        .iter()
        .zip(&envelope.raptorq.symbol_hashes)
    {
        let packet_bytes = STANDARD.decode(encoded)?;
        if packet_bytes.len() != 4 + usize::from(oti.symbol_size())
            || hash_bytes(&packet_bytes) != *expected_hash
        {
            return Err(DurabilityError::DecodeFailed);
        }
        let packet = EncodingPacket::deserialize(&packet_bytes);
        let block_number = u32::from(packet.payload_id().source_block_number());
        if block_number >= u32::from(oti.source_blocks())
            || !seen.insert((block_number, packet.payload_id().encoding_symbol_id()))
        {
            return Err(DurabilityError::DecodeFailed);
        }
        let source_symbols = if block_number < large_block_count {
            large_block_symbols
        } else {
            small_block_symbols
        };

        if packet.payload_id().encoding_symbol_id() < source_symbols {
            source_packets.push(packet);
        } else {
            repair_packets.push(packet);
        }
    }

    let observed_sources = u32::try_from(source_packets.len()).unwrap_or(u32::MAX);
    let observed_repairs = u32::try_from(repair_packets.len()).unwrap_or(u32::MAX);
    if observed_sources != envelope.raptorq.k || observed_repairs != envelope.raptorq.repair_symbols
    {
        return Err(DurabilityError::DecodeDrillPacketLayout {
            expected_sources: envelope.raptorq.k,
            expected_repairs: envelope.raptorq.repair_symbols,
            observed_sources,
            observed_repairs,
        });
    }

    Ok((source_packets, repair_packets))
}

fn prepare_source_loss_drill(
    envelope: &ArtifactEnvelope,
    sources: &[EncodingPacket],
    repairs: &[EncodingPacket],
) -> Result<(Vec<EncodingPacket>, Vec<SourcePacketLoss>), DurabilityError> {
    if sources.is_empty() {
        return Ok((Vec::new(), Vec::new()));
    }
    if repairs.is_empty() {
        return Err(DurabilityError::DecodeDrillNoRepairPackets);
    }
    let mut budget = BTreeMap::<u8, usize>::new();
    for packet in repairs {
        *budget
            .entry(packet.payload_id().source_block_number())
            .or_default() += 1;
    }
    let mut selected = sources
        .iter()
        .enumerate()
        .map(|(index, packet)| {
            let mut rank = blake3::Hasher::new();
            rank.update(b"fnx-source-loss-drill-v1\0");
            rank.update(envelope.source_hash.as_bytes());
            rank.update(&[packet.payload_id().source_block_number()]);
            rank.update(&packet.payload_id().encoding_symbol_id().to_be_bytes());
            (*rank.finalize().as_bytes(), index)
        })
        .collect::<Vec<_>>();
    selected.sort_unstable();
    let mut lost_indices = BTreeSet::new();
    for (_, index) in selected {
        let block = sources[index].payload_id().source_block_number();
        if let Some(remaining) = budget.get_mut(&block)
            && *remaining > 0
        {
            *remaining -= 1;
            lost_indices.insert(index);
        }
    }
    if lost_indices.is_empty() {
        return Err(DurabilityError::DecodeDrillNoRepairPackets);
    }
    let mut retained = Vec::with_capacity(sources.len() + repairs.len() - lost_indices.len());
    let mut lost = Vec::with_capacity(lost_indices.len());
    for (index, packet) in sources.iter().enumerate() {
        if lost_indices.contains(&index) {
            lost.push(SourcePacketLoss {
                source_block: packet.payload_id().source_block_number(),
                encoding_symbol_id: packet.payload_id().encoding_symbol_id(),
            });
        } else {
            retained.push(packet.clone());
        }
    }
    lost.sort_unstable_by_key(|packet| (packet.source_block, packet.encoding_symbol_id));
    retained.extend_from_slice(repairs);
    Ok((retained, lost))
}

fn verify_decode_drill_fail_closed(
    envelope: &ArtifactEnvelope,
    source_packets: &[EncodingPacket],
    dropped_packets: u32,
) -> Result<Option<u32>, DurabilityError> {
    if source_packets.is_empty() {
        return Ok(None);
    }

    match decode_with_binary_packets(
        envelope,
        source_packets[..source_packets.len() - 1].iter().cloned(),
    ) {
        Err(DurabilityError::DecodeFailed) => Ok(Some(dropped_packets + 1)),
        Err(err) => Err(err),
        Ok(_) => Err(DurabilityError::DecodeDrillFailOpen),
    }
}

fn decode_oti(oti_b64: &str) -> Result<ObjectTransmissionInformation, DurabilityError> {
    let oti_bytes = STANDARD.decode(oti_b64)?;
    let oti_slice: [u8; 12] = oti_bytes
        .as_slice()
        .try_into()
        .map_err(|_| DurabilityError::InvalidOtiLength)?;
    validate_oti(ObjectTransmissionInformation::deserialize(&oti_slice))
}

fn validate_oti(
    oti: ObjectTransmissionInformation,
) -> Result<ObjectTransmissionInformation, DurabilityError> {
    if oti.symbol_size() == 0
        || oti.source_blocks() == 0
        || oti.transfer_length() == 0
        || oti.transfer_length() > MAX_DURABILITY_FILE_SIZE as u64
        || oti.symbol_alignment() == 0
        || oti.sub_blocks() == 0
        || !oti
            .symbol_size()
            .is_multiple_of(u16::from(oti.symbol_alignment()))
        || oti.sub_blocks() > oti.symbol_size() / u16::from(oti.symbol_alignment())
    {
        return Err(DurabilityError::DecodeFailed);
    }
    let symbols = oti.transfer_length().div_ceil(u64::from(oti.symbol_size()));
    // RFC 6330 K'_max; the pinned RaptorQ decoder asserts this same ceiling.
    if symbols < u64::from(oti.source_blocks())
        || symbols.div_ceil(u64::from(oti.source_blocks())) > 56_403
    {
        return Err(DurabilityError::DecodeFailed);
    }
    Ok(oti)
}

fn source_packet_count_from_oti(config: &ObjectTransmissionInformation) -> u32 {
    u32::try_from(
        config
            .transfer_length()
            .div_ceil(u64::from(config.symbol_size())),
    )
    .unwrap_or(u32::MAX)
}

fn recovered_source_blocks(envelope: &ArtifactEnvelope) -> Result<u32, DurabilityError> {
    if envelope.raptorq.k == 0 {
        return Ok(0);
    }
    Ok(u32::from(
        decode_oti(&envelope.raptorq.oti_b64)?.source_blocks(),
    ))
}

fn decode_with_packets(
    envelope: &ArtifactEnvelope,
    packet_b64: &[String],
) -> Result<Vec<u8>, DurabilityError> {
    if envelope.raptorq.k == 0 {
        return Ok(Vec::new());
    }

    let oti = decode_oti(&envelope.raptorq.oti_b64)?;
    let mut decoder = Decoder::new(oti);

    for encoded in packet_b64 {
        let packet_bytes = STANDARD.decode(encoded)?;
        if packet_bytes.len() != 4 + usize::from(oti.symbol_size()) {
            return Err(DurabilityError::DecodeFailed);
        }
        let packet = EncodingPacket::deserialize(&packet_bytes);
        if packet.payload_id().source_block_number() >= oti.source_blocks() {
            return Err(DurabilityError::DecodeFailed);
        }
        if let Some(decoded) = decoder.decode(packet) {
            return Ok(decoded);
        }
    }

    Err(DurabilityError::DecodeFailed)
}

fn decode_with_binary_packets<I>(
    envelope: &ArtifactEnvelope,
    packets: I,
) -> Result<Vec<u8>, DurabilityError>
where
    I: IntoIterator<Item = EncodingPacket>,
{
    if envelope.raptorq.k == 0 {
        return Ok(Vec::new());
    }

    let oti = decode_oti(&envelope.raptorq.oti_b64)?;
    let mut decoder = Decoder::new(oti);
    for packet in packets {
        if let Some(decoded) = decoder.decode(packet) {
            return Ok(decoded);
        }
    }

    Err(DurabilityError::DecodeFailed)
}

fn hash_bytes(bytes: &[u8]) -> String {
    format!("blake3:{}", blake3::hash(bytes).to_hex())
}

fn unix_time_ms() -> u128 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or(Duration::from_millis(0))
        .as_millis()
}

impl fmt::Display for ScrubState {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Ok => write!(f, "ok"),
            Self::Recovered => write!(f, "recovered"),
            Self::Failed => write!(f, "failed"),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::{
        ArtifactEnvelope, DurabilityError, Encoder, EncodingPacket, ObjectTransmissionInformation,
        STANDARD, classify_decode_drill_packets, decode_oti, decode_with_binary_packets,
        decode_with_packets, generate_sidecar_for_file, partition, prepare_source_loss_drill,
        run_decode_drill, scrub_artifact, source_packet_count_from_oti,
        verify_decode_drill_fail_closed,
    };
    use base64::Engine;
    use std::fs;
    use tempfile::tempdir;

    fn generated_envelope(payload: &[u8], mtu: u16, repair_symbols: u32) -> ArtifactEnvelope {
        let temp = tempdir().expect("tempdir should be created");
        let artifact = temp.path().join("artifact.bin");
        let sidecar = temp.path().join("artifact.raptorq.json");
        fs::write(&artifact, payload).expect("artifact write should succeed");
        generate_sidecar_for_file(
            &artifact,
            &sidecar,
            "perf-artifact",
            "benchmark",
            mtu,
            repair_symbols,
        )
        .expect("sidecar generation should succeed")
    }

    fn source_packet_count_frozen(encoder: &Encoder) -> u32 {
        encoder
            .get_block_encoders()
            .iter()
            .map(|block| {
                u32::try_from(block.source_packets().len())
                    .expect("source packets per block should fit u32")
            })
            .sum()
    }

    fn encoded_packets_with_count(
        encoder: &Encoder,
        repair_per_block: u32,
        use_oti_count: bool,
    ) -> (u32, Vec<EncodingPacket>) {
        let source_packets = if use_oti_count {
            source_packet_count_from_oti(&encoder.get_config())
        } else {
            source_packet_count_frozen(encoder)
        };
        (
            source_packets,
            encoder.get_encoded_packets(repair_per_block),
        )
    }

    fn decode_drill_core_frozen(
        envelope: &ArtifactEnvelope,
    ) -> Result<(Vec<u8>, u32, Option<u32>), DurabilityError> {
        if envelope.raptorq.k == 0 {
            return Ok((Vec::new(), 0, None));
        }

        let oti = decode_oti(&envelope.raptorq.oti_b64)?;
        let total_source_packets =
            u32::try_from(oti.transfer_length().div_ceil(u64::from(oti.symbol_size())))
                .map_err(|_| DurabilityError::DecodeFailed)?;
        let (large_block_symbols, small_block_symbols, large_block_count, _) =
            partition(total_source_packets, u32::from(oti.source_blocks()));
        let mut source_packets = Vec::with_capacity(envelope.raptorq.k as usize);
        let mut repair_packets = Vec::with_capacity(envelope.raptorq.repair_symbols as usize);

        for encoded in &envelope.raptorq.packets_b64 {
            let packet_bytes = STANDARD.decode(encoded)?;
            let packet = EncodingPacket::deserialize(&packet_bytes);
            let block_number = u32::from(packet.payload_id().source_block_number());
            let source_symbols = if block_number < large_block_count {
                large_block_symbols
            } else {
                small_block_symbols
            };
            if packet.payload_id().encoding_symbol_id() < source_symbols {
                source_packets.push(encoded.clone());
            } else {
                repair_packets.push(encoded.clone());
            }
        }

        let dropped_packets = u32::try_from(repair_packets.len()).unwrap_or(u32::MAX);
        let recovered = decode_with_packets(envelope, &source_packets)?;
        let fail_closed_candidate = source_packets[..source_packets.len() - 1].to_vec();
        let fail_closed_beyond = match decode_with_packets(envelope, &fail_closed_candidate) {
            Err(DurabilityError::DecodeFailed) => Some(dropped_packets + 1),
            Err(err) => return Err(err),
            Ok(_) => return Err(DurabilityError::DecodeDrillFailOpen),
        };
        Ok((recovered, dropped_packets, fail_closed_beyond))
    }

    fn decode_drill_core_binary(
        envelope: &ArtifactEnvelope,
    ) -> Result<(Vec<u8>, u32, Option<u32>), DurabilityError> {
        // Retain the historical intact-source operation for the frozen
        // representation comparison below, not as a source-loss proof.
        let (source_packets, repair_packets) = classify_decode_drill_packets(envelope)?;
        let dropped_packets = u32::try_from(repair_packets.len()).unwrap_or(u32::MAX);
        let recovered = decode_with_binary_packets(envelope, source_packets.iter().cloned())?;
        let fail_closed_beyond =
            verify_decode_drill_fail_closed(envelope, &source_packets, dropped_packets)?;
        Ok((recovered, dropped_packets, fail_closed_beyond))
    }

    #[test]
    fn sidecar_generation_and_scrub_recovery_work() {
        let temp = tempdir().expect("tempdir should be created");
        let artifact = temp.path().join("artifact.json");
        let sidecar = temp.path().join("artifact.raptorq.json");
        fs::write(&artifact, b"{\"hello\":\"world\"}").expect("artifact write should succeed");

        let generated =
            generate_sidecar_for_file(&artifact, &sidecar, "artifact", "conformance", 1400, 4)
                .expect("sidecar generation should succeed");
        assert_eq!(generated.artifact_id, "artifact");
        assert!(generated.raptorq.k > 0);

        fs::write(&artifact, b"corrupted").expect("corruption write should succeed");
        let scrubbed = scrub_artifact(&artifact, &sidecar).expect("scrub recovery should succeed");
        assert_eq!(scrubbed.scrub.status, super::ScrubState::Recovered);

        let recovered_content = fs::read_to_string(&artifact).expect("read recovered");
        assert_eq!(recovered_content, "{\"hello\":\"world\"}");
    }

    #[test]
    fn generate_and_scrub_missing_artifact() {
        let temp = tempdir().expect("tempdir should be created");
        let artifact = temp.path().join("artifact.json");
        let sidecar = temp.path().join("artifact.raptorq.json");
        fs::write(&artifact, b"essential data").expect("artifact write");

        generate_sidecar_for_file(&artifact, &sidecar, "missing_test", "data", 1400, 4)
            .expect("generate");

        fs::remove_file(&artifact).expect("remove artifact");
        assert!(!artifact.exists());

        let scrubbed = scrub_artifact(&artifact, &sidecar).expect("recover missing");
        assert_eq!(scrubbed.scrub.status, super::ScrubState::Recovered);
        assert!(artifact.exists());
        assert_eq!(
            fs::read_to_string(&artifact).expect("artifact should be readable"),
            "essential data"
        );
    }

    #[test]
    fn scrub_recovery_uses_repairs_after_source_packet_loss() {
        let temp = tempdir().expect("tempdir");
        let artifact = temp.path().join("artifact.bin");
        let sidecar = temp.path().join("artifact.raptorq.json");
        let payload = (0_u8..=250).cycle().take(753).collect::<Vec<_>>();
        fs::write(&artifact, &payload).expect("source");
        let mut envelope = generate_sidecar_for_file(&artifact, &sidecar, "loss", "unit", 128, 6)
            .expect("sidecar");
        envelope.raptorq.packets_b64.remove(0);
        envelope.raptorq.symbol_hashes.remove(0);
        super::write_envelope(&sidecar, &envelope).expect("persist packet erasure");
        fs::write(&artifact, b"damaged source").expect("damage source fixture");
        let recovered = scrub_artifact(&artifact, &sidecar).expect("recover using actual repairs");
        assert_eq!(fs::read(&artifact).expect("recovered source"), payload);
        assert_eq!(
            recovered
                .decode_proofs
                .last()
                .expect("proof")
                .recovered_blocks,
            1
        );
        assert!(classify_decode_drill_packets(&envelope).is_err());
    }

    #[test]
    fn decode_drill_emits_recovered_output() {
        let temp = tempdir().expect("tempdir should be created");
        let artifact = temp.path().join("artifact.json");
        let sidecar = temp.path().join("artifact.raptorq.json");
        let recovered = temp.path().join("artifact.recovered.json");
        let payload = vec![b'x'; 4096];
        fs::write(&artifact, &payload).expect("artifact write should succeed");

        generate_sidecar_for_file(&artifact, &sidecar, "artifact", "conformance", 64, 6)
            .expect("sidecar generation should succeed");
        let post_drill =
            run_decode_drill(&sidecar, &recovered).expect("decode drill should succeed");
        assert!(!post_drill.decode_proofs.is_empty());
        assert_eq!(post_drill.scrub.status, super::ScrubState::Recovered);
        assert!(recovered.exists());
        assert_eq!(
            fs::read(&recovered).expect("recovered artifact should be readable"),
            payload
        );

        let decode_proof = post_drill
            .decode_proofs
            .last()
            .expect("decode proof should be recorded");
        assert_eq!(decode_proof.reason, "decode_drill_source_loss_success");
        assert_eq!(
            decode_proof.dropped_packets,
            Some(post_drill.raptorq.repair_symbols)
        );
        assert_eq!(
            decode_proof.fail_closed_beyond,
            Some(post_drill.raptorq.repair_symbols + 1)
        );
    }

    #[test]
    fn decode_drill_proof_accounts_for_actual_source_loss() {
        let temp = tempdir().expect("tempdir should be created");
        let artifact = temp.path().join("source.bin");
        let sidecar = temp.path().join("source.raptorq.json");
        let recovered = temp.path().join("source.recovered.bin");
        let payload = (0_u8..=250).cycle().take(4_096).collect::<Vec<_>>();
        fs::write(&artifact, &payload).expect("write source");
        generate_sidecar_for_file(&artifact, &sidecar, "source-loss", "fixture", 64, 6)
            .expect("generate source-loss sidecar");
        let drilled = run_decode_drill(&sidecar, &recovered).expect("recover source loss");
        assert_eq!(
            drilled
                .decode_proofs
                .last()
                .expect("proof")
                .recovered_blocks,
            1,
        );
        let proof = serde_json::to_value(drilled.decode_proofs.last().expect("drill proof"))
            .expect("serialize proof");
        assert_eq!(proof["reason"], "decode_drill_source_loss_success");
        assert!(
            proof["dropped_source_packets"]
                .as_array()
                .is_some_and(|packets| !packets.is_empty()),
            "a repair drill must identify original source packets that were absent"
        );
        assert_eq!(fs::read(&recovered).expect("read recovered"), payload);
        assert_eq!(fs::read(&artifact).expect("original retained"), payload);
    }

    #[test]
    fn source_loss_drill_needs_repairs_and_has_a_real_over_budget_negative() {
        for &(length, mtu) in &[(1, 64), (65, 64), (4_096, 64), (16_384, 256)] {
            let payload = (0_u8..=250).cycle().take(length).collect::<Vec<_>>();
            let envelope = generated_envelope(&payload, mtu, 6);
            let (mut sources, mut repairs) =
                classify_decode_drill_packets(&envelope).expect("classify valid packets");
            let (retained, lost) = prepare_source_loss_drill(&envelope, &sources, &repairs)
                .expect("select source loss");
            assert!(!lost.is_empty());
            assert!(lost.len() <= repairs.len());
            assert_eq!(retained.len(), sources.len() + repairs.len() - lost.len());
            assert_eq!(
                decode_with_binary_packets(&envelope, retained.iter().cloned())
                    .expect("recover using repairs"),
                payload,
            );
            let source_only = retained
                .iter()
                .filter(|packet| {
                    sources
                        .iter()
                        .any(|source| source.payload_id() == packet.payload_id())
                })
                .cloned();
            assert!(matches!(
                decode_with_binary_packets(&envelope, source_only),
                Err(DurabilityError::DecodeFailed),
            ));
            assert_eq!(
                verify_decode_drill_fail_closed(
                    &envelope,
                    &sources,
                    envelope.raptorq.repair_symbols
                )
                .expect("over-budget must fail closed"),
                Some(envelope.raptorq.repair_symbols + 1),
            );
            sources.reverse();
            repairs.reverse();
            let (permuted, permuted_loss) =
                prepare_source_loss_drill(&envelope, &sources, &repairs)
                    .expect("permuted selection");
            assert_eq!(lost, permuted_loss);
            assert_eq!(
                decode_with_binary_packets(&envelope, permuted).expect("permuted recovery"),
                payload,
            );
        }
        let no_repair = generated_envelope(b"requires actual repair data", 64, 0);
        let (sources, repairs) =
            classify_decode_drill_packets(&no_repair).expect("valid no-repair");
        assert!(matches!(
            prepare_source_loss_drill(&no_repair, &sources, &repairs),
            Err(DurabilityError::DecodeDrillNoRepairPackets),
        ));
        let empty = generated_envelope(b"", 64, 6);
        let (sources, repairs) = classify_decode_drill_packets(&empty).expect("empty layout");
        let (retained, lost) = prepare_source_loss_drill(&empty, &sources, &repairs)
            .expect("empty is explicitly not a source-loss proof");
        assert!(retained.is_empty() && lost.is_empty());
    }

    #[test]
    fn drill_rejects_corrupt_short_duplicate_and_zero_size_packets() {
        let payload = (0_u8..=250).cycle().take(1_025).collect::<Vec<_>>();
        let envelope = generated_envelope(&payload, 128, 6);
        let mut corrupted = envelope.clone();
        corrupted.raptorq.symbol_hashes[0] = "wrong packet hash".to_owned();
        assert!(matches!(
            classify_decode_drill_packets(&corrupted),
            Err(DurabilityError::DecodeFailed),
        ));
        let mut short = envelope.clone();
        short.raptorq.packets_b64[0] = STANDARD.encode([0]);
        short.raptorq.symbol_hashes[0] = super::hash_bytes(&[0]);
        assert!(matches!(
            classify_decode_drill_packets(&short),
            Err(DurabilityError::DecodeFailed),
        ));
        let mut duplicate = envelope.clone();
        duplicate.raptorq.packets_b64[1] = duplicate.raptorq.packets_b64[0].clone();
        duplicate.raptorq.symbol_hashes[1] = duplicate.raptorq.symbol_hashes[0].clone();
        assert!(matches!(
            classify_decode_drill_packets(&duplicate),
            Err(DurabilityError::DecodeFailed),
        ));
        let mut zero_size = envelope;
        zero_size.raptorq.oti_b64 = STANDARD.encode([0; 12]);
        assert!(matches!(
            classify_decode_drill_packets(&zero_size),
            Err(DurabilityError::DecodeFailed),
        ));
        for index in [8, 9, 10, 11] {
            let mut malformed = generated_envelope(&payload, 128, 6);
            let mut oti = STANDARD
                .decode(&malformed.raptorq.oti_b64)
                .expect("OTI bytes");
            oti[index] = 0;
            if index == 9 || index == 10 {
                oti[9] = 0;
                oti[10] = 0;
            }
            malformed.raptorq.oti_b64 = STANDARD.encode(oti);
            assert!(matches!(
                classify_decode_drill_packets(&malformed),
                Err(DurabilityError::DecodeFailed),
            ));
        }
    }

    #[test]
    fn invalid_mtu_is_an_error_not_an_encoder_panic() {
        let temp = tempdir().expect("tempdir");
        let payload = temp.path().join("payload.bin");
        let sidecar = temp.path().join("sidecar.json");
        fs::write(&payload, b"nonempty").expect("payload");
        assert!(matches!(
            generate_sidecar_for_file(&payload, &sidecar, "id", "fixture", 0, 6),
            Err(DurabilityError::InvalidMtu),
        ));
        assert!(!sidecar.exists());
    }

    #[test]
    fn default_encoding_rejects_wrapped_source_block_counts() {
        for block_count in [256_u64, 257] {
            let oti =
                ObjectTransmissionInformation::with_defaults((block_count - 1) * 56_403 + 1, 1);
            assert!(matches!(
                super::validate_oti(oti),
                Err(DurabilityError::DecodeFailed),
            ));
        }
        let temp = tempdir().expect("tempdir");
        let payload = temp.path().join("payload.bin");
        let sidecar = temp.path().join("sidecar.json");
        let bytes = vec![b'a'; 255 * 56_403 + 1];
        fs::write(&payload, &bytes).expect("write bounded payload");
        assert!(matches!(
            generate_sidecar_for_file(&payload, &sidecar, "id", "unit", 1, 0),
            Err(DurabilityError::InvalidEncodingParameters),
        ));
        assert!(!sidecar.exists());
        assert_eq!(fs::read(&payload).expect("original retained"), bytes);
    }

    #[test]
    fn small_mtu_still_encodes_admitted_payloads() {
        let temp = tempdir().expect("tempdir");
        let payload = temp.path().join("payload.bin");
        let sidecar = temp.path().join("sidecar.json");
        let bytes = b"small but nonempty";
        fs::write(&payload, bytes).expect("payload");
        let envelope = generate_sidecar_for_file(&payload, &sidecar, "id", "unit", 1, 6)
            .expect("valid small MTU must not be blanket-rejected");
        assert_eq!(
            decode_with_packets(&envelope, &envelope.raptorq.packets_b64)
                .expect("decode valid small MTU"),
            bytes,
        );
    }

    #[test]
    fn source_loss_is_accounted_per_block() {
        let payload = (0_u8..=250).cycle().take(1_025).collect::<Vec<_>>();
        let oti = ObjectTransmissionInformation::new(1_025, 128, 3, 1, 8);
        let encoder = Encoder::new(&payload, oti);
        let packets = encoder.get_encoded_packets(6);
        let serialized = packets
            .iter()
            .map(EncodingPacket::serialize)
            .collect::<Vec<_>>();
        let mut envelope = generated_envelope(&payload, 128, 6);
        envelope.raptorq.k = source_packet_count_from_oti(&oti);
        envelope.raptorq.repair_symbols = packets.len() as u32 - envelope.raptorq.k;
        envelope.raptorq.oti_b64 = STANDARD.encode(oti.serialize());
        envelope.raptorq.packets_b64 = serialized
            .iter()
            .map(|packet| STANDARD.encode(packet))
            .collect();
        envelope.raptorq.symbol_hashes = serialized
            .iter()
            .map(|packet| super::hash_bytes(packet))
            .collect();
        let (sources, repairs) =
            classify_decode_drill_packets(&envelope).expect("multi-block layout");
        let (retained, lost) =
            prepare_source_loss_drill(&envelope, &sources, &repairs).expect("per-block loss");
        for block in 0..3 {
            assert_eq!(
                lost.iter()
                    .filter(|packet| packet.source_block == block)
                    .count(),
                3
            );
        }
        assert_eq!(
            decode_with_binary_packets(&envelope, retained).expect("multi-block repair"),
            payload
        );
        assert_eq!(
            verify_decode_drill_fail_closed(&envelope, &sources, envelope.raptorq.repair_symbols)
                .expect("multi-block negative"),
            Some(envelope.raptorq.repair_symbols + 1)
        );
    }

    fn release_manifest_fixture(root: &std::path::Path) -> std::path::PathBuf {
        // These are unit-test payloads, not claims that a public release has
        // supplied the real five classes of production evidence.
        let members = super::RELEASE_EVIDENCE_CLASSES
            .iter()
            .enumerate()
            .map(|(index, class)| {
                let path = format!("class-{index}.bin");
                let bytes = format!("unit fixture for {class}").into_bytes();
                fs::write(root.join(&path), &bytes).expect("write unit input");
                super::ReleaseEvidenceMember {
                    class: (*class).to_owned(),
                    path,
                    source_hash: super::hash_bytes(&bytes),
                }
            })
            .collect();
        let manifest = super::ReleaseEvidenceManifest {
            schema: "fnx-release-evidence-input-v1".to_owned(),
            members,
        };
        let path = root.join("manifest.json");
        fs::write(
            &path,
            serde_json::to_vec(&manifest).expect("serialize manifest"),
        )
        .expect("write manifest");
        path
    }

    #[test]
    fn release_bundle_preserves_inputs_and_reexecutes_recovery() {
        let temp = tempdir().expect("tempdir");
        let manifest = release_manifest_fixture(temp.path());
        let bundle_dir = temp.path().join("bundle");
        let candidate = "a".repeat(64);
        let bundle =
            super::prepare_release_evidence(temp.path(), &manifest, &bundle_dir, &candidate)
                .expect("prepare actual unit payloads");
        assert_eq!(bundle.members.len(), 5);
        let checked =
            super::verify_release_evidence(&bundle_dir, &candidate).expect("fresh decode");
        assert_eq!(checked.candidate_id, candidate);
        assert!(super::verify_release_evidence(&bundle_dir, &"b".repeat(64)).is_err());
        assert!(
            super::prepare_release_evidence(temp.path(), &manifest, &bundle_dir, &candidate)
                .is_err()
        );
        for (index, record) in bundle.members.iter().enumerate() {
            let directory = bundle_dir.join(format!("{index:05}"));
            let original =
                fs::read(temp.path().join(&record.member.path)).expect("original retained");
            assert_eq!(
                original,
                fs::read(directory.join("payload.bin")).expect("payload")
            );
            assert_eq!(
                original,
                fs::read(directory.join("recovered.bin")).expect("recovery")
            );
            assert!(directory.join("scrub.json").is_file());
            let envelope =
                super::read_envelope(&directory.join("payload.raptorq.json")).expect("proof");
            assert!(
                !envelope.decode_proofs[0]
                    .dropped_source_packets
                    .as_ref()
                    .expect("source loss")
                    .is_empty()
            );
        }
        fs::write(bundle_dir.join("00000/recovered.bin"), b"tampered").expect("tamper recovery");
        assert!(super::verify_release_evidence(&bundle_dir, &candidate).is_err());
    }

    #[test]
    fn release_manifest_rejects_stale_missing_duplicate_and_traversal_inputs() {
        let temp = tempdir().expect("tempdir");
        let manifest_path = release_manifest_fixture(temp.path());
        let manifest: super::ReleaseEvidenceManifest =
            serde_json::from_slice(&fs::read(&manifest_path).expect("read manifest"))
                .expect("parse manifest");
        let candidate = "a".repeat(64);
        for kind in 0..4 {
            let mut bad = manifest.clone();
            match kind {
                0 => bad.members[0].source_hash = super::hash_bytes(b"stale"),
                1 => {
                    bad.members.pop();
                }
                2 => bad.members[0].path = bad.members[1].path.clone(),
                _ => bad.members[0].path = "../outside.bin".to_owned(),
            }
            let path = temp.path().join(format!("bad-{kind}.json"));
            let output = temp.path().join(format!("bad-bundle-{kind}"));
            fs::write(
                &path,
                serde_json::to_vec(&bad).expect("serialize bad input"),
            )
            .expect("write bad input");
            assert!(
                super::prepare_release_evidence(temp.path(), &path, &output, &candidate).is_err()
            );
            assert!(
                !output.join("bundle.json").exists(),
                "no completion on failure"
            );
        }
    }

    #[cfg(unix)]
    #[test]
    fn release_bundle_rejects_linked_input_and_bundle_directories() {
        let temp = tempdir().expect("tempdir");
        let manifest = release_manifest_fixture(temp.path());
        let candidate = "a".repeat(64);
        let bundle = temp.path().join("bundle");
        super::prepare_release_evidence(temp.path(), &manifest, &bundle, &candidate)
            .expect("bundle");
        let linked = temp.path().join("linked-bundle");
        std::os::unix::fs::symlink(&bundle, &linked).expect("link fixture");
        assert!(super::verify_release_evidence(&linked, &candidate).is_err());
        let input_link = temp.path().join("linked-input.bin");
        std::os::unix::fs::symlink(temp.path().join("class-0.bin"), &input_link)
            .expect("link input");
        let mut input: super::ReleaseEvidenceManifest =
            serde_json::from_slice(&fs::read(&manifest).expect("manifest bytes"))
                .expect("manifest");
        input.members[0].path = "linked-input.bin".to_owned();
        let linked_manifest = temp.path().join("linked-manifest.json");
        fs::write(
            &linked_manifest,
            serde_json::to_vec(&input).expect("linked manifest"),
        )
        .expect("write manifest");
        assert!(
            super::prepare_release_evidence(
                temp.path(),
                &linked_manifest,
                &temp.path().join("rejected"),
                &candidate
            )
            .is_err()
        );
    }

    #[test]
    fn binary_decode_drill_core_matches_frozen_representation() {
        let payload = (0_u8..=250).cycle().take(16_384).collect::<Vec<_>>();
        let envelope = generated_envelope(&payload, 256, 12);

        let frozen = decode_drill_core_frozen(&envelope).expect("frozen drill should succeed");
        let binary = decode_drill_core_binary(&envelope).expect("binary drill should succeed");
        assert_eq!(binary, frozen);
        assert_eq!(binary.0, payload);
    }

    #[test]
    fn oti_source_packet_count_matches_materialized_packets() {
        for &(payload_len, mtu) in &[(1usize, 64u16), (63, 64), (64, 64), (65, 64), (16_384, 128)] {
            let payload = (0_u8..=250).cycle().take(payload_len).collect::<Vec<_>>();
            let encoder = Encoder::with_defaults(&payload, mtu);
            assert_eq!(
                source_packet_count_from_oti(&encoder.get_config()),
                source_packet_count_frozen(&encoder),
            );
        }

        let payload = (0_u8..=250).cycle().take(1_025).collect::<Vec<_>>();
        let multi_block_oti = ObjectTransmissionInformation::new(1_025, 128, 3, 1, 8);
        let multi_block = Encoder::new(&payload, multi_block_oti);
        assert_eq!(multi_block.get_block_encoders().len(), 3);
        assert_eq!(
            source_packet_count_from_oti(&multi_block.get_config()),
            source_packet_count_frozen(&multi_block),
        );

        let payload = (0_u8..=250).cycle().take(16_384).collect::<Vec<_>>();
        let mtu = 128;
        let repairs = 12;
        let envelope = generated_envelope(&payload, mtu, repairs);
        let encoder = Encoder::with_defaults(&payload, mtu);
        let frozen_k = source_packet_count_frozen(&encoder);
        let blocks = u32::try_from(encoder.get_block_encoders().len())
            .expect("source block count should fit u32");
        let repair_per_block = repairs.div_ceil(blocks);
        let packets = encoder.get_encoded_packets(repair_per_block);
        let serialized = packets
            .iter()
            .map(EncodingPacket::serialize)
            .collect::<Vec<_>>();
        let expected_hashes = serialized
            .iter()
            .map(|bytes| super::hash_bytes(bytes))
            .collect::<Vec<_>>();
        let expected_b64 = serialized
            .iter()
            .map(|bytes| STANDARD.encode(bytes))
            .collect::<Vec<_>>();
        let expected_repairs =
            u32::try_from(packets.len()).expect("packet count should fit u32") - frozen_k;

        assert_eq!(envelope.raptorq.k, frozen_k);
        assert_eq!(envelope.raptorq.repair_symbols, expected_repairs);
        assert_eq!(envelope.raptorq.symbol_hashes, expected_hashes);
        assert_eq!(envelope.raptorq.packets_b64, expected_b64);
        assert_eq!(
            envelope.raptorq.overhead_ratio.to_bits(),
            (f64::from(expected_repairs) / f64::from(frozen_k)).to_bits(),
        );
    }

    /// Same-binary paired A/B for the source-packet count inside sidecar
    /// generation. The frozen arm materializes every source packet once to
    /// count it before both arms perform the identical real packet build.
    #[test]
    #[ignore = "measurement; run with --profile release --ignored --nocapture"]
    fn oti_source_packet_count_ab() {
        use std::hint::black_box;
        use std::time::Instant;

        let payload = (0_u8..=250).cycle().take(524_288).collect::<Vec<_>>();
        let encoder = Encoder::with_defaults(&payload, 128);
        let repair_per_block = 32;
        let frozen = encoded_packets_with_count(&encoder, repair_per_block, false);
        let candidate = encoded_packets_with_count(&encoder, repair_per_block, true);
        assert_eq!(candidate, frozen);
        println!(
            "DURABILITY_OTI_COUNT_AB fixture: bytes={} blocks={} source_packets={} repair_per_block={repair_per_block}",
            payload.len(),
            encoder.get_block_encoders().len(),
            candidate.0,
        );

        let calls = 8usize;
        let rounds = 15usize;
        let time = |use_oti_count: bool| {
            let started = Instant::now();
            for _ in 0..calls {
                black_box(encoded_packets_with_count(
                    &encoder,
                    repair_per_block,
                    use_oti_count,
                ));
            }
            started.elapsed().as_nanos()
        };
        for _ in 0..3 {
            black_box(time(false));
            black_box(time(true));
        }

        let paired = |candidate: bool, baseline: bool| {
            let mut baseline_ns = Vec::with_capacity(rounds);
            let mut candidate_ns = Vec::with_capacity(rounds);
            for round in 0..rounds {
                let (base, cand) = if round % 2 == 0 {
                    (time(baseline), time(candidate))
                } else {
                    let cand = time(candidate);
                    let base = time(baseline);
                    (base, cand)
                };
                baseline_ns.push(base);
                candidate_ns.push(cand);
            }
            (baseline_ns, candidate_ns)
        };
        let median = |samples: &[u128]| {
            let mut sorted = samples.to_vec();
            sorted.sort_unstable();
            sorted[sorted.len() / 2]
        };
        let report = |name: &str, baseline_ns: &[u128], candidate_ns: &[u128]| {
            let baseline_median = median(baseline_ns);
            let candidate_median = median(candidate_ns);
            let wins = baseline_ns
                .iter()
                .zip(candidate_ns)
                .filter(|(baseline, candidate)| baseline > candidate)
                .count();
            println!(
                "DURABILITY_OTI_COUNT_AB {name}: baseline_median_ns={baseline_median} \
                 candidate_median_ns={candidate_median} ratio={:.4}x wins={wins}/{rounds}",
                baseline_median as f64 / candidate_median as f64,
            );
        };

        let (baseline_ns, candidate_ns) = paired(true, false);
        report(
            "materialized_count_vs_oti_count",
            &baseline_ns,
            &candidate_ns,
        );
        let (null_a_ns, null_b_ns) = paired(true, true);
        report("oti_count_vs_oti_count_null", &null_a_ns, &null_b_ns);
    }

    /// Historical intact-source representation comparison, NOT a benchmark
    /// of the production source-loss drill. The frozen
    /// arm retains the former base64 String partitions and repeats base64
    /// decode/deserialization in both decoder passes; the candidate retains
    /// classified binary packets and clones their payload bytes for reuse.
    #[test]
    #[ignore = "measurement; run with --profile release --ignored --nocapture"]
    fn decode_drill_binary_packet_reuse_ab() {
        use std::hint::black_box;
        use std::time::Instant;

        let payload = (0_u8..=250).cycle().take(131_072).collect::<Vec<_>>();
        let envelope = generated_envelope(&payload, 512, 32);
        let frozen = decode_drill_core_frozen(&envelope).expect("frozen drill should succeed");
        let binary = decode_drill_core_binary(&envelope).expect("binary drill should succeed");
        assert_eq!(binary, frozen);
        assert_eq!(binary.0, payload);
        println!(
            "DURABILITY_BINARY_PACKET_AB fixture: bytes={} source_packets={} repair_packets={}",
            payload.len(),
            envelope.raptorq.k,
            envelope.raptorq.repair_symbols,
        );

        let calls = 2usize;
        let rounds = 15usize;
        let time = |reuse_binary: bool| {
            let started = Instant::now();
            for _ in 0..calls {
                let result = if reuse_binary {
                    decode_drill_core_binary(&envelope)
                } else {
                    decode_drill_core_frozen(&envelope)
                }
                .expect("decode drill core should succeed");
                black_box(result);
            }
            started.elapsed().as_nanos()
        };
        for _ in 0..3 {
            black_box(time(false));
            black_box(time(true));
        }

        let paired = |candidate: bool, baseline: bool| {
            let mut baseline_ns = Vec::with_capacity(rounds);
            let mut candidate_ns = Vec::with_capacity(rounds);
            for round in 0..rounds {
                let (base, cand) = if round % 2 == 0 {
                    (time(baseline), time(candidate))
                } else {
                    let cand = time(candidate);
                    let base = time(baseline);
                    (base, cand)
                };
                baseline_ns.push(base);
                candidate_ns.push(cand);
            }
            (baseline_ns, candidate_ns)
        };
        let median = |samples: &[u128]| {
            let mut sorted = samples.to_vec();
            sorted.sort_unstable();
            sorted[sorted.len() / 2]
        };
        let report = |name: &str, baseline_ns: &[u128], candidate_ns: &[u128]| {
            let baseline_median = median(baseline_ns);
            let candidate_median = median(candidate_ns);
            let wins = baseline_ns
                .iter()
                .zip(candidate_ns)
                .filter(|(baseline, candidate)| baseline > candidate)
                .count();
            println!(
                "DURABILITY_BINARY_PACKET_AB {name}: baseline_median_ns={baseline_median} \
                 candidate_median_ns={candidate_median} ratio={:.4}x wins={wins}/{rounds}",
                baseline_median as f64 / candidate_median as f64,
            );
        };

        let (baseline_ns, candidate_ns) = paired(true, false);
        report(
            "base64_redecode_vs_binary_reuse",
            &baseline_ns,
            &candidate_ns,
        );
        let (null_a_ns, null_b_ns) = paired(true, true);
        report("binary_reuse_vs_binary_reuse_null", &null_a_ns, &null_b_ns);
    }
}
