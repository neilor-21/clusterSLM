import argparse
import json
import time
from pathlib import Path
from language_adapters import scan_repository
from resolver import build_symbol_index, resolve_call_graph, resolve_import_graph_edges
from graph import build_symbol_graph
from partition import partition_graph
from boundary import find_boundaries
from analyzer import export_partition_contexts, mock_slm_worker, build_partition_context
from static_analyzer import analyze_partition_context
from model_worker import HuggingFaceModelWorker
from reconciler import reconcile_findings
from reporter import generate_report


def main():
    cli = argparse.ArgumentParser(
        description="Analyze a repository with the current ClusterSLM pipeline."
    )
    cli.add_argument("repository", help="Path to the repository to analyze")
    cli.add_argument(
        "--export", action="store_true",
        help="Export partition contexts for external model inference and stop",
    )
    cli.add_argument(
        "--findings", type=Path, default=None, metavar="PATH",
        help="Optional JSON findings file from external model inference; bypasses the selected engine.",
    )
    cli.add_argument(
        "--engine", choices=("mock", "static", "model", "hybrid"), default="static",
        help="Detection engine: static heuristic baseline (default), model, hybrid, or legacy mock.",
    )
    cli.add_argument("--model-id", default="Qwen/Qwen2.5-Coder-1.5B-Instruct",
                     help="Hugging Face model ID for --engine model/hybrid.")
    cli.add_argument("--adapter", default=None, help="Optional fine-tuned PEFT/LoRA adapter directory.")
    cli.add_argument("--load-in-4bit", action="store_true", help="Use 4-bit model loading where supported.")
    cli.add_argument("--max-new-tokens", type=int, default=700, help="Maximum generated tokens per partition.")
    cli.add_argument("--max-input-tokens", type=int, default=8192, help="Maximum context tokens sent to the model per partition.")
    args = cli.parse_args()
    analysis_started = time.perf_counter()
    repo_path = Path(args.repository).resolve()
    export_mode = args.export

    # 1.0 Repository Ingestion & Parsing
    scan = scan_repository(repo_path)
    files = scan.parsed_files
    print(f"\nRepository: {repo_path}")
    print(f"Source files detected: {scan.source_file_count}")
    if scan.detected_languages:
        print("Detected languages:")
        for language, count in scan.detected_languages.items():
            status = "parsed" if language in scan.parsed_languages else "detected only"
            print(f"  - {language}: {count} file(s) ({status})")
    else:
        print("No recognized source files found.")
    print(f"Files parsed for structural analysis: {len(files)}")
    if scan.unsupported_files:
        print(f"Languages awaiting parser adapters: {len(scan.unsupported_files)} file(s)")
    if scan.skipped_files:
        print(f"Files skipped due to parsing/read errors: {len(scan.skipped_files)}")

    # 2.0 Dependency Graph Construction (Level 3)
    index = build_symbol_index(files, repo_path)
    edges = resolve_call_graph(files, repo_path, index)
    import_edges = resolve_import_graph_edges(files, repo_path)
    symbol_graph = build_symbol_graph(
        edges, dependency_edges=import_edges, files=files, repo_path=repo_path
    )
    print(f"Resolved call edges: {sum(1 for _, _, data in symbol_graph.edges(data=True) if data.get('relation') == 'CALLS')}")
    print(f"Resolved repository-local import edges: {len(import_edges)}")

    # 3.0 Graph-Guided Repository Partitioning
    partitions = partition_graph(symbol_graph)
    boundaries = find_boundaries(symbol_graph, partitions)

    if export_mode:
        # Export mode: generate the payload for Kaggle
        export_partition_contexts(partitions, boundaries, files, repo_path)
        print(
            "[+] Contexts prepared. Upload 'partition_contexts.json' to Kaggle for Process 4.0."
        )
        return

    if args.findings is not None:
        findings_file = args.findings.resolve()
        if not findings_file.is_file():
            cli.error(f"Findings file does not exist: {findings_file}")
        print(f"\n[+] Loading external findings from {findings_file}...")
        with findings_file.open("r", encoding="utf-8") as f:
            findings = json.load(f)
        if not isinstance(findings, list):
            cli.error("Findings JSON must contain a top-level list.")
    else:
        print(f"\n[+] Detection engine: {args.engine}")
        findings = []
        model_worker = None
        if args.engine in {"model", "hybrid"}:
            model_worker = HuggingFaceModelWorker(
                model_id=args.model_id,
                adapter_path=args.adapter,
                max_new_tokens=args.max_new_tokens,
                max_input_tokens=args.max_input_tokens,
                load_in_4bit=args.load_in_4bit,
            )
        for p in partitions:
            ctx = build_partition_context(p, boundaries, files, repo_path)
            if args.engine == "mock":
                res = mock_slm_worker(ctx)
            elif args.engine == "static":
                res = analyze_partition_context(ctx)
            elif args.engine == "model":
                res = model_worker(ctx)
            else:  # hybrid: static rules plus SLM suggestions; reconciliation deduplicates.
                static_result = analyze_partition_context(ctx)
                model_result = model_worker(ctx)
                res = {"partition_id": p["partition_id"],
                       "findings": static_result["findings"] + model_result["findings"]}
            if res.get("findings"):
                findings.append(res)

    reconciled = reconcile_findings(findings, boundaries, partitions)
    elapsed_seconds = time.perf_counter() - analysis_started
    generate_report(reconciled, execution_seconds=elapsed_seconds)


if __name__ == "__main__":
    main()
