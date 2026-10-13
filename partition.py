import networkx as nx
from networkx.algorithms.community import greedy_modularity_communities


def partition_graph(graph):
    """
    Process 3.0: Graph-Guided Repository Partitioning.
    Uses modularity-based community detection to find natural clusters.
    """
    # Community detection requires edges; preserve isolated modules as singleton
    # partitions instead of allowing modularity calculation to divide by zero.
    if graph.number_of_nodes() == 0:
        return []
    if graph.number_of_edges() == 0:
        return [
            {"partition_id": i + 1, "nodes": [node], "subgraph": graph.subgraph([node]).copy()}
            for i, node in enumerate(sorted(graph.nodes()))
        ]

    # Community detection algorithms generally require an undirected graph
    undirected_graph = graph.to_undirected()

    # Discover communities based purely on edge density
    communities = greedy_modularity_communities(undirected_graph)

    partitions = []
    for i, comm in enumerate(communities):
        # Extract the directed subgraph for this partition
        subgraph = graph.subgraph(comm).copy()
        partitions.append(
            {"partition_id": i + 1, "nodes": list(comm), "subgraph": subgraph}
        )

    return partitions


def print_partitions(partitions):
    print("\n" + "=" * 50)
    print("PROCESS 3.0: GRAPH-GUIDED PARTITIONS")
    print("=" * 50)

    for p in partitions:
        print(f"\nPartition {p['partition_id']} ({len(p['nodes'])} nodes):")
        # Print sorted nodes so it's easy to read
        for node in sorted(p["nodes"]):
            print(f"  - {node}")
