"""Phase 0 探索脚本：用真实/确定性 RAG 链路探索中文全文语料的回答覆盖度与排序短板。

默认 deterministic（不依赖真实 API），可用 ``--real`` 走 .env 配置的真实 MIMO + Jina；
真实模式带轻量重试，真实失败显式记录到 CSV ``error`` 字段，不静默掩盖。

输出 ``data/evaluation/stage19_exploration_results.csv``：
每条 query 一行，记录 top-8 source_type 分布、深度全文/题录占比、
首条深度全文命中名次、回答覆盖关键词命中数、refused、耗时和真实 API 错误。

不调用任何写入型操作；不修改数据库。
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402
from app.db.session import SessionLocal, init_db  # noqa: E402
from app.services.brain.config import RetrievalConfig  # noqa: E402
from app.services.brain.service import BrainService  # noqa: E402
from app.services.brain.workflow import BrainAnswerResult  # noqa: E402
from app.services.generation.chat_model import (  # noqa: E402
    ChatModelProvider,
    create_chat_model_provider,
)
from app.services.retrieval.embedding import EmbeddingProvider  # noqa: E402
from app.services.retrieval.hybrid_search import HybridSearchService  # noqa: E402
from scripts.evaluate_chat import chat_model_name_for_provider  # noqa: E402
from scripts.evaluate_vector_search import create_embedding_provider_from_settings  # noqa: E402


DEEP_FULLTEXT_TYPES = {"open_access_pdf", "institutional_access_pdf"}
METADATA_TYPES = {"metadata_record"}

RESULT_FIELDS = [
    "query_id",
    "query",
    "intent",
    "config_mode",
    "top_k",
    "retrieval_mode_actual",
    "refused",
    "refusal_reason",
    "source_types_top8",
    "deep_fulltext_in_top8",
    "metadata_in_top8",
    "rank_first_deep_fulltext",
    "rank_first_metadata",
    "top_source_titles",
    "citations_count",
    "expected_keywords",
    "coverage_keywords_hit",
    "coverage_keywords_total",
    "answer_excerpt",
    "duration_s",
    "model_provider",
    "model_name",
    "error",
    "notes",
]


@dataclass(frozen=True)
class ExplorationQuery:
    query_id: str
    query: str
    intent: str  # "on_topic" | "refusal_expected"
    expected_keywords: tuple[str, ...]
    notes: str


# 8 on-topic + 2 需拒答 = 10 题；on-topic 覆盖填充能力/对比/SCC/ITZ/温控/抗冻/工程案例/纤维改性
QUERIES: tuple[ExplorationQuery, ...] = (
    ExplorationQuery(
        query_id="cn_explore_filling_capacity",
        query="堆石混凝土的填充能力受哪些因素影响？",
        intent="on_topic",
        expected_keywords=("填充", "自密实", "流动", "空隙", "粒径"),
        notes="跨段证据：自密实流动性 + 堆石级配 + 空隙率",
    ),
    ExplorationQuery(
        query_id="cn_explore_rfc_vs_rcc",
        query="堆石混凝土与碾压混凝土在材料组成和施工工艺上有什么区别？",
        intent="on_topic",
        expected_keywords=("堆石", "碾压", "自密实", "施工", "工艺"),
        notes="易混淆术语：RFC vs RCC",
    ),
    ExplorationQuery(
        query_id="cn_explore_scc_role",
        query="自密实混凝土在堆石混凝土中起到什么作用？",
        intent="on_topic",
        expected_keywords=("自密实", "流动", "填充", "堆石"),
        notes="基本概念：SCC 的作用",
    ),
    ExplorationQuery(
        query_id="cn_explore_itz_strength",
        query="堆石混凝土的界面过渡区对抗压强度有什么影响？",
        intent="on_topic",
        expected_keywords=("界面", "过渡区", "ITZ", "抗压", "强度"),
        notes="参数细节 + 微观结构（承接阶段 16 ITZ 议题）",
    ),
    ExplorationQuery(
        query_id="cn_explore_temperature_control",
        query="堆石混凝土在大体积浇筑时如何进行温控防裂？",
        intent="on_topic",
        expected_keywords=("温度", "温控", "水化", "裂缝", "大体积"),
        notes="跨段证据：水化热 + 温控措施 + 裂缝控制",
    ),
    ExplorationQuery(
        query_id="cn_explore_freeze_thaw",
        query="堆石混凝土的抗冻性能如何评价？",
        intent="on_topic",
        expected_keywords=("抗冻", "冻融", "耐久", "循环"),
        notes="参数细节：抗冻指标",
    ),
    ExplorationQuery(
        query_id="cn_explore_engineering_cases",
        query="堆石混凝土坝有哪些工程应用案例？",
        intent="on_topic",
        expected_keywords=("工程", "应用", "坝", "案例", "施工"),
        notes="工程案例类",
    ),
    ExplorationQuery(
        query_id="cn_explore_fiber_tailings",
        query="加入钢纤维或铁尾矿对堆石混凝土性能有什么影响？",
        intent="on_topic",
        expected_keywords=("钢纤维", "尾矿", "性能", "强度"),
        notes="跨段证据 + 改性材料",
    ),
    ExplorationQuery(
        query_id="cn_explore_refusal_mix_design",
        query="请判断本工程的堆石混凝土配合比设计是否符合规范？",
        intent="refusal_expected",
        expected_keywords=(),
        notes="工程责任判断，应当拒答（系统提示不替代规范审查）",
    ),
    ExplorationQuery(
        query_id="cn_explore_refusal_weather",
        query="今天上海的天气怎么样？",
        intent="refusal_expected",
        expected_keywords=(),
        notes="off-topic，应当拒答（主题门 has_topic_anchor）",
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--real",
        action="store_true",
        help="使用 .env 配置的真实 MIMO+Jina；默认 deterministic。",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=8,
        help="每条 query 返回 top-K 检索结果与 Brain 上下文，默认 8。",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="真实模式下的轻量重试次数（仅 --real 生效），默认 3。",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=str(ROOT / "data" / "evaluation" / "stage19_exploration_results.csv"),
        help="输出 CSV 路径。",
    )
    parser.add_argument(
        "--queries-jsonl",
        type=str,
        default="",
        help="可选：从 JSONL 读取额外探索 query（每行含 query_id/query/intent/expected_keywords/notes）。",
    )
    return parser.parse_args()


def load_extra_queries(path_str: str) -> list[ExplorationQuery]:
    if not path_str:
        return []
    path = Path(path_str)
    if not path.exists():
        return []
    extras: list[ExplorationQuery] = []
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            extras.append(
                ExplorationQuery(
                    query_id=str(obj["query_id"]),
                    query=str(obj["query"]),
                    intent=str(obj.get("intent", "on_topic")),
                    expected_keywords=tuple(obj.get("expected_keywords", [])),
                    notes=str(obj.get("notes", "")),
                )
            )
    return extras


def build_providers(real: bool) -> tuple[ChatModelProvider, EmbeddingProvider, str]:
    settings = get_settings()
    if real:
        if not (settings.chat_model_provider and settings.embedding_provider):
            raise RuntimeError(
                "real mode requires CHAT_MODEL_PROVIDER and EMBEDDING_PROVIDER in .env"
            )
        chat = create_chat_model_provider(
            provider_name=settings.chat_model_provider,
            model_name=settings.chat_model_name,
            api_key=settings.chat_model_api_key,
            base_url=settings.chat_model_base_url,
            temperature=settings.chat_model_temperature,
            timeout_seconds=max(settings.chat_model_timeout_seconds, 60.0),
        )
        embed = create_embedding_provider_from_settings(
            provider_name=settings.embedding_provider,
            settings=settings,
        )
        return chat, embed, "real"
    chat = create_chat_model_provider(provider_name="deterministic")
    embed = create_embedding_provider_from_settings(
        provider_name="deterministic",
        settings=settings,
    )
    return chat, embed, "deterministic"


def count_in_top_k(source_types: list[str], wanted: set[str]) -> int:
    return sum(1 for st in source_types if st in wanted)


def first_rank(source_types: list[str], wanted: set[str]) -> int:
    for index, st in enumerate(source_types, start=1):
        if st in wanted:
            return index
    return 0  # 0 = not found


def count_keyword_hits(answer: str, keywords: tuple[str, ...]) -> int:
    if not keywords:
        return 0
    lowered = answer.lower()
    return sum(1 for kw in keywords if kw.lower() in lowered)


def run_once(
    brain: BrainService,
    hybrid: HybridSearchService,
    query: ExplorationQuery,
    top_k: int,
) -> tuple[BrainAnswerResult, list[str], list[str]]:
    hybrid_results = hybrid.search(query=query.query, top_k=top_k)
    source_types = [r.source_type for r in hybrid_results]
    top_titles = [r.document_title for r in hybrid_results]
    config = RetrievalConfig(retrieval_mode="hybrid", top_k=top_k)
    answer = brain.answer(question=query.query, config=config)
    return answer, source_types, top_titles


def explore_query(
    brain: BrainService,
    hybrid: HybridSearchService,
    query: ExplorationQuery,
    top_k: int,
    config_mode: str,
    retries: int,
    settings,
) -> dict[str, str]:
    attempts = max(1, retries) if config_mode == "real" else 1
    last_error: str = ""
    start_ts = time.monotonic()
    answer: BrainAnswerResult | None = None
    source_types: list[str] = []
    top_titles: list[str] = []
    for attempt in range(1, attempts + 1):
        try:
            answer, source_types, top_titles = run_once(brain, hybrid, query, top_k)
            last_error = ""
            break
        except Exception as exc:
            last_error = (
                f"attempt={attempt}/{attempts} type={type(exc).__name__} msg={str(exc)[:200]}"
            )
            if attempt < attempts:
                time.sleep(min(2.0 * attempt, 10.0))
            continue
    duration = round(time.monotonic() - start_ts, 3)

    if answer is None:
        return {
            "query_id": query.query_id,
            "query": query.query,
            "intent": query.intent,
            "config_mode": config_mode,
            "top_k": str(top_k),
            "retrieval_mode_actual": "error",
            "refused": "",
            "refusal_reason": "",
            "source_types_top8": "",
            "deep_fulltext_in_top8": "",
            "metadata_in_top8": "",
            "rank_first_deep_fulltext": "",
            "rank_first_metadata": "",
            "top_source_titles": "",
            "citations_count": "",
            "expected_keywords": ";".join(query.expected_keywords),
            "coverage_keywords_hit": "",
            "coverage_keywords_total": str(len(query.expected_keywords)),
            "answer_excerpt": "",
            "duration_s": str(duration),
            "model_provider": "",
            "model_name": chat_model_name_for_provider(None, settings) or "",
            "error": last_error,
            "notes": query.notes,
        }

    deep_count = count_in_top_k(source_types, DEEP_FULLTEXT_TYPES)
    meta_count = count_in_top_k(source_types, METADATA_TYPES)
    excerpt = (answer.answer or "")[:200].replace("\n", " ").strip()
    return {
        "query_id": query.query_id,
        "query": query.query,
        "intent": query.intent,
        "config_mode": config_mode,
        "top_k": str(top_k),
        "retrieval_mode_actual": answer.retrieval_mode,
        "refused": str(answer.refused).lower(),
        "refusal_reason": (answer.refusal_reason or "")[:200],
        "source_types_top8": ";".join(source_types),
        "deep_fulltext_in_top8": str(deep_count),
        "metadata_in_top8": str(meta_count),
        "rank_first_deep_fulltext": str(first_rank(source_types, DEEP_FULLTEXT_TYPES)),
        "rank_first_metadata": str(first_rank(source_types, METADATA_TYPES)),
        "top_source_titles": " | ".join(t[:80] for t in top_titles),
        "citations_count": str(len(answer.citations)),
        "expected_keywords": ";".join(query.expected_keywords),
        "coverage_keywords_hit": str(count_keyword_hits(excerpt, query.expected_keywords)),
        "coverage_keywords_total": str(len(query.expected_keywords)),
        "answer_excerpt": excerpt,
        "duration_s": str(duration),
        "model_provider": answer.model_provider or "",
        "model_name": answer.model_name or "",
        "error": last_error,
        "notes": query.notes,
    }


def write_results(out_path: Path, rows: list[dict[str, str]]) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def print_summary(rows: list[dict[str, str]], out_path: Path, config_mode: str) -> None:
    total = len(rows)
    refused = sum(1 for r in rows if r["refused"] == "true")
    refusal_expected = sum(1 for r in rows if r["intent"] == "refusal_expected")
    refusal_matched = sum(
        1
        for r in rows
        if (r["intent"] == "refusal_expected" and r["refused"] == "true")
        or (r["intent"] == "on_topic" and r["refused"] == "false")
    )
    on_topic_rows = [r for r in rows if r["intent"] == "on_topic" and r["refused"] == "false"]
    deep_top1 = sum(1 for r in on_topic_rows if r["rank_first_deep_fulltext"] == "1")
    meta_top1 = sum(1 for r in on_topic_rows if r["rank_first_metadata"] == "1")
    errors = sum(1 for r in rows if r["error"])
    print(f"stage19 exploration ({config_mode}) -> {out_path}")
    print(f"  total={total} refused={refused} (expected={refusal_expected})")
    print(f"  refusal_matched={refusal_matched}/{total}")
    print(f"  on_topic_answered={len(on_topic_rows)} deep_top1={deep_top1} metadata_top1={meta_top1}")
    print(f"  errors={errors}")


def main() -> None:
    args = parse_args()
    settings = get_settings()
    init_db()

    chat, embed, config_mode = build_providers(real=args.real)
    queries = list(QUERIES) + load_extra_queries(args.queries_jsonl)

    rows: list[dict[str, str]] = []
    with SessionLocal() as db:
        brain = BrainService(db=db, chat_model_provider=chat, embedding_provider=embed, log_answers=False)
        hybrid = HybridSearchService(db=db, embedding_provider=embed)
        for query in queries:
            row = explore_query(brain, hybrid, query, args.top_k, config_mode, args.retries, settings)
            rows.append(row)

    out_path = Path(args.out)
    write_results(out_path, rows)
    print_summary(rows, out_path, config_mode)


if __name__ == "__main__":
    main()
