import networkx as nx


def reconcile_findings(findings_list, boundaries, partitions):
    """
    Process 5.0: Boundary-Aware Reconciliation.
    Cross-references SLM findings with the cross-partition dependency graph
    by tracing paths through the partition's internal subgraph.
    """
    print("\n" + "=" * 50)
    print("PROCESS 5.0: BOUNDARY-AWARE RECONCILIATION")
    print("=" * 50)

    # Create a quick lookup for partitions
    partition_map = {p["partition_id"]: p for p in partitions}

    all_issues = []
    for f in findings_list:
        for issue in f["findings"]:
            # Normalize legacy mock payloads (`function`) to the canonical `symbol` key.
            if "symbol" not in issue and "function" in issue:
                issue["symbol"] = issue["function"]
            issue["partition_id"] = f["partition_id"]
            all_issues.append(issue)

    # Merge duplicate reports from static and model engines by exact symbol/CWE.
    # Keep the strongest confidence, retain detector provenance, and avoid claiming
    # that two engines independently prove exploitability.
    def confidence_of(item):
        try:
            return float(item.get("confidence", 0))
        except (TypeError, ValueError):
            return 0.0

    deduplicated = {}
    for issue in all_issues:
        key = (issue.get("symbol", issue.get("function", "<unknown>")), issue.get("cwe", ""))
        if key not in deduplicated:
            deduplicated[key] = dict(issue)
            continue
        previous = deduplicated[key]
        detectors = set(str(previous.get("detector", "unknown")).split(","))
        detectors.update(str(issue.get("detector", "unknown")).split(","))
        if confidence_of(issue) > confidence_of(previous):
            deduplicated[key] = dict(issue)
        chosen = deduplicated[key]
        chosen["detector"] = ",".join(sorted(x for x in detectors if x))
        chosen["validation_status"] = "needs_review"
    all_issues = list(deduplicated.values())

    reconciled_results = []

    for issue in all_issues:
        print(
            f"\nAnalyzing finding: {issue['vulnerability']} in {issue['symbol']} (Partition {issue['partition_id']})"
        )

        part_id = issue["partition_id"]
        target_func = issue.get("symbol", issue.get("function", "<unknown>"))
        issue["symbol"] = target_func
        subgraph = partition_map[part_id]["subgraph"]

        incoming_vectors = []

        # Scan all boundary edges that enter this partition
        for b in boundaries:
            if b["target_partition"] == part_id:
                entry_node = b["target_node"]

                # Check if there is a path from the boundary entry point to the vulnerability
                if entry_node in subgraph and target_func in subgraph:
                    if nx.has_path(subgraph, entry_node, target_func):
                        path = nx.shortest_path(subgraph, entry_node, target_func)
                        incoming_vectors.append(
                            {
                                "source_node": b["source_node"],
                                "source_partition": b["source_partition"],
                                "entry_node": entry_node,
                                "internal_path": path,
                            }
                        )

        if incoming_vectors:
            print("  [!] WARNING: Cross-Partition Vulnerability Chain Detected!")
            for v in incoming_vectors:
                print(
                    f"      Source: Partition {v['source_partition']} ({v['source_node']})"
                )
                print(f"      Entered Partition {part_id} at: {v['entry_node']}")
                print(f"      Internal Path to Sink: {' -> '.join(v['internal_path'])}")

            issue["cross_boundary"] = True
            issue["vectors"] = incoming_vectors
        else:
            print(
                "  [-] Localized vulnerability (No external partition triggers found)."
            )
            issue["cross_boundary"] = False

        reconciled_results.append(issue)

    return reconciled_results
