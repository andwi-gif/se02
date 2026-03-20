from __future__ import annotations

import argparse
import json
from pathlib import Path

from quantum_api_drift_lab.orchestrator import run_experiment
from quantum_api_drift_lab.ui.gradio_app import create_app



def main() -> None:
    parser = argparse.ArgumentParser(description="Quantum API Drift Lab")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run an experiment")
    run_parser.add_argument("--config", default="configs/experiment.demo.yaml")
    run_parser.add_argument("--mode", default=None)
    run_parser.add_argument("--backend", default=None)
    run_parser.add_argument("--run-name", default=None)
    run_parser.add_argument("--models", nargs="*", default=None)
    run_parser.add_argument("--strategies", nargs="*", default=None)

    serve_parser = subparsers.add_parser("serve", help="Launch the Gradio demo UI")
    serve_parser.add_argument("--config", default="configs/experiment.demo.yaml")
    serve_parser.add_argument("--server-name", default="127.0.0.1")
    serve_parser.add_argument("--server-port", type=int, default=7860)

    args = parser.parse_args()
    if args.command == "run":
        artifact = run_experiment(
            Path(args.config),
            override_mode=args.mode,
            override_backend=args.backend,
            override_run_name=args.run_name,
            enabled_model_names=args.models,
            enabled_strategies=args.strategies,
            log_fn=print,
        )
        print(json.dumps(artifact.to_dict(), indent=2))
        return

    if args.command == "serve":
        app = create_app(Path(args.config))
        app.launch(server_name=args.server_name, server_port=args.server_port, show_error=True)
        return


if __name__ == "__main__":
    main()
