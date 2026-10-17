use fnx_durability::{
    generate_sidecar_for_file, prepare_release_evidence, run_decode_drill, scrub_artifact,
    verify_release_evidence,
};
use std::path::PathBuf;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<String> = std::env::args().collect();
    if args.len() < 2 {
        eprintln!(
            "usage:\n  fnx-durability generate <artifact> <sidecar> <artifact_id> <artifact_type> [mtu] [repair]\n  fnx-durability scrub <artifact> <sidecar>\n  fnx-durability decode-drill <sidecar> <recovered_output>\n  fnx-durability release-bundle <manifest> <payload_root> <new_bundle_dir> <candidate_id>\n  fnx-durability verify-release-bundle <bundle_dir> <candidate_id>"
        );
        std::process::exit(2);
    }

    match args[1].as_str() {
        "generate" => {
            if args.len() < 6 {
                eprintln!(
                    "generate requires: <artifact> <sidecar> <artifact_id> <artifact_type> [mtu] [repair]"
                );
                std::process::exit(2);
            }
            let artifact = PathBuf::from(&args[2]);
            let sidecar = PathBuf::from(&args[3]);
            let artifact_id = &args[4];
            let artifact_type = &args[5];
            let mtu = args
                .get(6)
                .map(|value| value.parse::<u16>())
                .transpose()?
                .unwrap_or(1400);
            let repair = args
                .get(7)
                .map(|value| value.parse::<u32>())
                .transpose()?
                .unwrap_or(6);

            let envelope = generate_sidecar_for_file(
                &artifact,
                &sidecar,
                artifact_id,
                artifact_type,
                mtu,
                repair,
            )?;
            println!(
                "generated sidecar: artifact_id={} source_hash={} packets={}",
                envelope.artifact_id,
                envelope.source_hash,
                envelope.raptorq.packets_b64.len()
            );
        }
        "scrub" => {
            if args.len() < 4 {
                eprintln!("scrub requires: <artifact> <sidecar>");
                std::process::exit(2);
            }
            let artifact = PathBuf::from(&args[2]);
            let sidecar = PathBuf::from(&args[3]);
            let envelope = scrub_artifact(&artifact, &sidecar)?;
            println!(
                "scrub status: {:?}, decode_proofs={}",
                envelope.scrub.status,
                envelope.decode_proofs.len()
            );
        }
        "decode-drill" => {
            if args.len() < 4 {
                eprintln!("decode-drill requires: <sidecar> <recovered_output>");
                std::process::exit(2);
            }
            let sidecar = PathBuf::from(&args[2]);
            let recovered_output = PathBuf::from(&args[3]);
            let envelope = run_decode_drill(&sidecar, &recovered_output)?;
            println!(
                "decode drill complete: recovered_output={} decode_proofs={}",
                recovered_output.display(),
                envelope.decode_proofs.len()
            );
        }
        "release-bundle" if args.len() == 6 => {
            let bundle = prepare_release_evidence(
                &PathBuf::from(&args[3]),
                &PathBuf::from(&args[2]),
                &PathBuf::from(&args[4]),
                &args[5],
            )?;
            println!("{}", serde_json::to_string(&bundle)?);
        }
        "verify-release-bundle" if args.len() == 4 => {
            let bundle = verify_release_evidence(&PathBuf::from(&args[2]), &args[3])?;
            println!("{}", serde_json::to_string(&bundle)?);
        }
        _ => {
            eprintln!("unknown command: {}", args[1]);
            std::process::exit(2);
        }
    }

    Ok(())
}
