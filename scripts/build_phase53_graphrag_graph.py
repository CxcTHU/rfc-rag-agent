from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from app.services.graphrag.graph_store import (
    build_knowledge_graph,
    graph_stats,
    load_extraction_results,
    prune_isolated_nodes_by_type,
    save_graph,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a Phase 53 NetworkX GraphRAG graph.")
    parser.add_argument("--input", required=True, help="Extraction JSON from extract_phase53_graphrag_triples.py")
    parser.add_argument("--output", default="data/evaluation/phase53_graphrag_graph.json")
    parser.add_argument("--stats-output", default="")
    parser.add_argument(
        "--prune-isolated-value-nodes",
        action="store_true",
        help="Remove degree-zero Value nodes before saving graph and stats.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    results = load_extraction_results(Path(args.input))
    graph = build_knowledge_graph(results)
    pruned_isolated_value_nodes = 0
    if args.prune_isolated_value_nodes:
        pruned_isolated_value_nodes = prune_isolated_nodes_by_type(graph, node_types={"Value"})
    output_path = Path(args.output)
    save_graph(graph, output_path)
    stats = graph_stats(graph).to_dict()
    if args.prune_isolated_value_nodes:
        stats["pruned_isolated_value_nodes"] = pruned_isolated_value_nodes
    if args.stats_output:
        write_stats(Path(args.stats_output), stats)
    print(json.dumps({"output": str(output_path), **stats}, ensure_ascii=False))
    return 0


def write_stats(path: Path, stats: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.casefold() == ".csv":
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["metric", "value"])
            writer.writeheader()
            for key, value in stats.items():
                if isinstance(value, dict):
                    writer.writerow({"metric": key, "value": json.dumps(value, ensure_ascii=False, sort_keys=True)})
                else:
                    writer.writerow({"metric": key, "value": value})
        return
    path.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
