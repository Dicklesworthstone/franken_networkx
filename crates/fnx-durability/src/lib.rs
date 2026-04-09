#![forbid(unsafe_code)]

use base64::Engine;
use base64::engine::general_purpose::STANDARD;
use raptorq::{Decoder, Encoder, EncodingPacket, ObjectTransmissionInformation};
use serde::{Deserialize, Serialize};
use std::fmt;
use std::fs;
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
    #[error("decode failed: insufficient or invalid packets")]
    DecodeFailed,
    #[error("decoded payload hash mismatch with source hash")]
    HashMismatch,
}

pub const MAX_DURABILITY_FILE_SIZE: usize = 100 * 1024 * 1024; // 100MB

pub fn generate_sidecar_for_file(
    artifact_path: &Path,
    sidecar_path: &Path,
    artifact_id: &str,
    artifact_type: &str,
    mtu: u16,
    repair_symbols: u32,
) -> Result<ArtifactEnvelope, DurabilityError> {
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
    let encoder = Encoder::with_defaults(&data, mtu);
    let config = encoder.get_config();

    let mut total_k = 0u32;
    for block_encoder in encoder.get_block_encoders() {
        total_k += block_encoder.source_packets().len() as u32;
    }

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
        recovered_blocks: envelope.raptorq.k,
        proof_hash: recovered_hash.clone(),
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
    let packets = envelope.raptorq.packets_b64.clone();

    let drop_count = usize::try_from(envelope.raptorq.repair_symbols.min(2)).unwrap_or(0);
    let reduced: Vec<String> = packets.into_iter().skip(drop_count).collect();

    let (recovered, reason) = match decode_with_packets(&envelope, &reduced) {
        Ok(data) => (data, "decode_drill_reduced"),
        Err(_) => (decode_from_envelope(&envelope)?, "decode_drill_full"),
    };

    let recovered_hash = hash_bytes(&recovered);
    if recovered_hash != envelope.source_hash {
        return Err(DurabilityError::HashMismatch);
    }

    fs::write(recovered_output, &recovered)?;
    let proof = DecodeProof {
        ts_unix_ms: unix_time_ms(),
        reason: reason.to_owned(),
        recovered_blocks: envelope.raptorq.k,
        proof_hash: recovered_hash.clone(),
    };
    envelope.decode_proofs.push(proof);
    envelope.scrub = ScrubStatus {
        last_ok_unix_ms: unix_time_ms(),
        status: ScrubState::Recovered,
    };
    write_envelope(sidecar_path, &envelope)?;
    Ok(envelope)
}

pub fn read_envelope(path: &Path) -> Result<ArtifactEnvelope, DurabilityError> {
    let raw = fs::read_to_string(path)?;
    Ok(serde_json::from_str(&raw)?)
}

pub fn write_envelope(path: &Path, envelope: &ArtifactEnvelope) -> Result<(), DurabilityError> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    fs::write(path, serde_json::to_string_pretty(envelope)?)?;
    Ok(())
}

fn decode_from_envelope(envelope: &ArtifactEnvelope) -> Result<Vec<u8>, DurabilityError> {
    decode_with_packets(envelope, &envelope.raptorq.packets_b64)
}

fn decode_with_packets(
    envelope: &ArtifactEnvelope,
    packet_b64: &[String],
) -> Result<Vec<u8>, DurabilityError> {
    let oti_bytes = STANDARD.decode(&envelope.raptorq.oti_b64)?;
    let oti_slice: [u8; 12] = oti_bytes
        .as_slice()
        .try_into()
        .map_err(|_| DurabilityError::InvalidOtiLength)?;
    let oti = ObjectTransmissionInformation::deserialize(&oti_slice);
    let mut decoder = Decoder::new(oti);

    for encoded in packet_b64 {
        let packet_bytes = STANDARD.decode(encoded)?;
        let packet = EncodingPacket::deserialize(&packet_bytes);
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
    use super::{generate_sidecar_for_file, run_decode_drill, scrub_artifact};
    use std::fs;
    use tempfile::tempdir;

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
    fn decode_drill_emits_recovered_output() {
        let temp = tempdir().expect("tempdir should be created");
        let artifact = temp.path().join("artifact.json");
        let sidecar = temp.path().join("artifact.raptorq.json");
        let recovered = temp.path().join("artifact.recovered.json");
        fs::write(&artifact, b"{\"x\":1}").expect("artifact write should succeed");

        generate_sidecar_for_file(&artifact, &sidecar, "artifact", "conformance", 1400, 4)
            .expect("sidecar generation should succeed");
        let post_drill =
            run_decode_drill(&sidecar, &recovered).expect("decode drill should succeed");
        assert!(!post_drill.decode_proofs.is_empty());
        assert!(recovered.exists());
    }
}
