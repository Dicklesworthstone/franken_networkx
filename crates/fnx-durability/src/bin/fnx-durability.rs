use fnx_durability::{generate_sidecar_for_file, run_decode_drill, scrub_artifact};
use std::path::PathBuf;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<String> = std::env::args().collect();
    if args.len() < 2 {
        eprintln!(
            "usage:\n  fnx-durability generate <artifact> <sidecar> <artifact_id> <artifact_type> [mtu] [repair]\n  fnx-durability scrub <artifact> <sidecar>\n  fnx-durability decode-drill <sidecar> <recovered_output>"
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
                .and_then(|value| value.parse::<u16>().ok())
                .unwrap_or(1400);
            let repair = args
                .get(7)
                .and_then(|value| value.parse::<u32>().ok())
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
        _ => {
            eprintln!("unknown command: {}", args[1]);
            std::process::exit(2);
        }
    }

    Ok(())
}
