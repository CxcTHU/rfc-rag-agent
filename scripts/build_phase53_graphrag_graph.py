from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.services.graphrag.graph_store import (
    build_knowledge_graph,
    graph_stats,
    load_extraction_results,
    save_graph,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a Phase 53 NetworkX GraphRAG graph.")
    parser.add_argument("--input", required=True, help="Extraction JSON from extract_phase53_graphrag_triples.py")
    parser.add_argument("--output", default="data/evaluation/phase53_graphrag_graph.json")
    parser.add_argument("--stats-output", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    results = load_extraction_results(Path(args.input))
    graph = build_knowledge_graph(results)
    output_path = Path(args.output)
    save_graph(graph, output_path)
    stats = graph_stats(graph).to_dict()
    if args.stats_output:
        stats_path = Path(args.stats_output)
        stats_path.parent.mkdir(parents=True, exist_ok=True)
        stats_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output_path), **stats}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
