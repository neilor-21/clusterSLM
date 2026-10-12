import argparse
import json
from pathlib import Path
from language_adapters import scan_repository
from resolver import build_symbol_index, resolve_call_graph
from graph import build_symbol_graph
from partition import partition_graph
from boundary import find_boundaries
from analyzer import export_partition_contexts, mock_slm_worker
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
        help="Optional JSON findings file from external model inference. If omitted, the mock detector is used.",
    )
    args = cli.parse_args()
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
    symbol_graph = build_symbol_graph(edges)

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
        print("\n[-] No --findings file supplied. Running mock SLM...")
        findings = []
        for p in partitions:
            from analyzer import build_partition_context, mock_slm_worker

            ctx = build_partition_context(p, boundaries, files, repo_path)
            res = mock_slm_worker(ctx)
            if res["findings"]:
                findings.append(res)

    reconciled = reconcile_findings(findings, boundaries, partitions)
    generate_report(reconciled)


if __name__ == "__main__":
    main()
