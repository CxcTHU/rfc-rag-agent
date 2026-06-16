from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db.repositories import SourceRepository  # noqa: E402
from app.db.session import SessionLocal, init_db  # noqa: E402
from app.services.ingestion.service import IngestionConfig, IngestionService  # noqa: E402
from app.services.source_collection import CSV_FIELDS, SourceCandidate, sanitize_filename  # noqa: E402
from app.services.source_registry import SourceRegistryService  # noqa: E402


METADATA_ONLY_TERMS = (
    "metadata_only; public bibliographic/scope-level record; full text requires "
    "legal purchase, official open publication, or institutional access"
)


@dataclass(frozen=True)
class ChineseStandardRecord:
    source_id: str
    standard_no: str
    title: str
    english_title: str
    authority: str
    year: str
    issue_date: str
    implementation_date: str
    status: str
    standard_class: str
    url: str
    category: str
    scope_summary: str
    keywords: str
    notes: str
    replacement: str = ""


STANDARDS: tuple[ChineseStandardRecord, ...] = (
    ChineseStandardRecord(
        source_id="std_cn_nb_t_10077_2018",
        standard_no="NB/T 10077-2018",
        title="堆石混凝土筑坝技术导则",
        english_title="Technical guide for rock-filled concrete dams",
        authority="国家能源局",
        year="2018",
        issue_date="2018",
        implementation_date="2019-03-01",
        status="现行；公开题录/引用信息入库",
        standard_class="能源行业标准",
        url="https://www.researchgate.net/profile/Feng-Jin-29/post/What-ia-the-disadvantages-of-two-stage-concrete/attachment/60120c20b425ca00016eaa2f/AS%3A984755801690112%401611795487346/download/English%2Bversion%2Bof%2BGuideline%2Bto%2BRFC%2Bdams.pdf",
        category="standard_document;rfc_standard;dam_engineering;design;construction_quality",
        scope_summary=(
            "堆石混凝土坝专门技术导则。当前仅入库公开题录、标准号、英文题名和参考文献信息；"
            "全文不作为开放语料自动收集。"
        ),
        keywords="堆石混凝土;堆石混凝土坝;rock-filled concrete;RFC dam;自密实混凝土;筑坝技术",
        notes=(
            "用户原需求中的 RFC 专门导则应优先映射到 NB/T 10077-2018；"
            "Engineering 综述文献亦将其列为 National Energy Administration 标准。"
        ),
    ),
    ChineseStandardRecord(
        source_id="std_cn_dl_t_5806_2020",
        standard_no="DL/T 5806-2020",
        title="水电水利工程堆石混凝土施工规范",
        english_title="Code for construction of rock-filled concrete in hydropower and water resources projects",
        authority="国家能源局",
        year="2020",
        issue_date="2020-10-23",
        implementation_date="2021-02-01",
        status="现行",
        standard_class="电力行业标准",
        url="https://hbba.sacinfo.org.cn/stdDetail/206fa5475f25d3967bb0f6abcfe0fe2c3ac5804d0dce3d783aa4438da6681be3",
        category="standard_document;rfc_standard;construction;quality_control;hydropower",
        scope_summary=(
            "全国标准信息公共服务平台备案题录显示，本标准为水电水利工程堆石混凝土施工规范，"
            "发布日期 2020-10-23，实施日期 2021-02-01。"
        ),
        keywords="堆石混凝土施工;水电水利工程;施工规范;质量控制;DL/T 5806",
        notes="高优先级 RFC 施工标准；只保存公开题录和范围级摘要。",
    ),
    ChineseStandardRecord(
        source_id="std_cn_gb_50496_2018",
        standard_no="GB 50496-2018",
        title="大体积混凝土施工标准",
        english_title="Standard for construction of mass concrete",
        authority="住房和城乡建设部；国家市场监督管理总局",
        year="2018",
        issue_date="2018-04-25",
        implementation_date="2018-12-01",
        status="现行",
        standard_class="国家标准",
        url="https://www.gongbiaoku.com/mobile/book/6lg19106hjw",
        category="standard_document;mass_concrete;thermal_control;construction",
        scope_summary=(
            "大体积混凝土施工通用国家标准，公开公告显示编号为 GB 50496-2018，"
            "自 2018-12-01 实施；与堆石混凝土的水化热、温控和施工控制问题相关。"
        ),
        keywords="大体积混凝土;温度控制;水化热;施工标准;GB 50496",
        notes=(
            "用户写作 GB/T 50496-2018；公开公告中标准编号为 GB 50496-2018。"
        ),
        replacement="GB 50496-2009",
    ),
    ChineseStandardRecord(
        source_id="std_cn_sl_t_352_2020",
        standard_no="SL/T 352-2020",
        title="水工混凝土试验规程",
        english_title="Test code for hydraulic concrete",
        authority="水利部",
        year="2020",
        issue_date="2020-11-30",
        implementation_date="2021-02-28",
        status="现行",
        standard_class="水利行业标准",
        url="https://std.samr.gov.cn/hb/search/stdHBDetailed?id=D02D254C62E40D3BE05397BE0A0A60C1",
        category="standard_document;hydraulic_concrete;testing;quality_control",
        scope_summary=(
            "水工混凝土试验和检测规程，全国标准信息公共服务平台题录显示其替代 SL 352-2006；"
            "与堆石混凝土原材料、拌合物、现场混凝土和质量检测问题相关。"
        ),
        keywords="水工混凝土;试验规程;质量检测;全级配混凝土;SL/T 352",
        notes="用户列作 SL 352-2020；备案题录标准号为 SL/T 352-2020。",
        replacement="SL 352-2006",
    ),
    ChineseStandardRecord(
        source_id="std_cn_dl_t_5330_2015",
        standard_no="DL/T 5330-2015",
        title="水工混凝土配合比设计规程",
        english_title="Code for mix design of hydraulic concrete",
        authority="国家能源局",
        year="2015",
        issue_date="2015-04-02",
        implementation_date="2015-09-01",
        status="现行",
        standard_class="电力行业标准",
        url="https://www.biaozhun.org/guojia/48676.html",
        category="standard_document;hydraulic_concrete;mix_design;self_compacting_concrete",
        scope_summary=(
            "适用于水电水利工程水工混凝土及砂浆配合比设计；"
            "对堆石混凝土所用自密实混凝土/水工混凝土配合比设计具有背景参考价值。"
        ),
        keywords="水工混凝土;配合比设计;砂浆;自密实混凝土;DL/T 5330",
        notes="公开题录显示由国家能源局发布，替代 DL/T 5330-2005。",
        replacement="DL/T 5330-2005",
    ),
    ChineseStandardRecord(
        source_id="std_cn_sl_314_2018",
        standard_no="SL 314-2018",
        title="碾压混凝土坝设计规范",
        english_title="Design specification for roller compacted concrete dams",
        authority="水利部",
        year="2018",
        issue_date="2018-07-17",
        implementation_date="2018-10-17",
        status="现行；RFC 需求纠错/对照标准",
        standard_class="水利行业标准",
        url="https://std.samr.gov.cn/hb/search/stdHBDetailed?id=8B1827F14B17BB19E05397BE0A0AB44A",
        category="standard_document;roller_compacted_concrete;dam_design;comparison_standard",
        scope_summary=(
            "公开标准平台题录显示 SL 314-2018 为碾压混凝土坝设计规范，不是堆石混凝土坝技术导则。"
            "入库目的是支持检索纠错和 RFC/RCC 对照，不把它标为 RFC 专门标准。"
        ),
        keywords="碾压混凝土坝;RCC dam;设计规范;SL 314;纠错;对照标准",
        notes=(
            "纠错记录：用户原列表将 SL 314-2018 写为《堆石混凝土坝技术导则》，"
            "但公开平台显示其题名为《碾压混凝土坝设计规范》。"
        ),
        replacement="SL 314-2004",
    ),
    ChineseStandardRecord(
        source_id="std_cn_db52_t_1545_2020",
        standard_no="DB52/T 1545-2020",
        title="堆石混凝土拱坝技术规范",
        english_title="Technical code for rock-filled concrete arch dams",
        authority="贵州省市场监督管理局",
        year="2020",
        issue_date="2020-12-16",
        implementation_date="2021-04-01",
        status="已废止；历史地方标准",
        standard_class="贵州省地方标准",
        url="https://dbba.sacinfo.org.cn/stdDetail/1fc2793f32ed3c23b03197f0be7a2c3610121173f2b639bffc48b8bec844c6fe",
        category="standard_document;rfc_standard;arch_dam;local_standard;historical",
        scope_summary=(
            "贵州地方标准，公开平台题录显示 2020-12-16 发布、2021-04-01 实施、"
            "2026-03-30 废止；适合保留为历史工程/地方标准背景。"
        ),
        keywords="堆石混凝土拱坝;地方标准;贵州;DB52/T 1545;历史标准",
        notes="低于国家/行业标准优先级；检索时应提示其已废止状态。",
    ),
)


RESULT_FIELDS = [
    "source_id",
    "standard_no",
    "title",
    "status",
    "document_id",
    "chunk_count",
    "card_path",
    "registry_status",
]


def standard_markdown(record: ChineseStandardRecord) -> str:
    lines = [
        f"# {record.standard_no}《{record.title}》",
        "",
        "> 本卡片仅包含公开题录、范围级摘要、纠错说明和检索关键词；不包含受版权或购买限制的标准正文条文。",
        "",
        "## 题录",
        "",
        f"- source_id: {record.source_id}",
        f"- standard_no: {record.standard_no}",
        f"- chinese_title: {record.title}",
        f"- english_title: {record.english_title}",
        f"- authority: {record.authority}",
        f"- standard_class: {record.standard_class}",
        f"- year: {record.year}",
        f"- issue_date: {record.issue_date}",
        f"- implementation_date: {record.implementation_date}",
        f"- status: {record.status}",
        f"- replacement: {record.replacement or 'unknown'}",
        f"- url: {record.url}",
        f"- access_rights: metadata_only",
        f"- license_or_terms: {METADATA_ONLY_TERMS}",
        "",
        "## 范围级摘要",
        "",
        record.scope_summary,
        "",
        "## Keywords",
        "",
        record.keywords,
        "",
        "## Notes",
        "",
        record.notes,
        "",
    ]
    return "\n".join(lines)


def candidate_from_standard(record: ChineseStandardRecord, card_path: Path, status: str) -> SourceCandidate:
    return SourceCandidate(
        source_id=record.source_id,
        title=f"{record.standard_no}《{record.title}》",
        authors=record.authority,
        year=record.year,
        venue=record.standard_class,
        category=record.category,
        discovered_via="stage40_chinese_standards_metadata",
        url=record.url,
        abstract=record.scope_summary,
        keywords=record.keywords,
        language="zh",
        source_type="standard_document",
        access_rights="metadata",
        license_or_terms=METADATA_ONLY_TERMS,
        local_path=str(card_path),
        status=status,
        notes=record.notes,
    )


def write_candidates_manifest(path: Path, candidates: list[SourceCandidate]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for candidate in candidates:
            writer.writerow(candidate.to_row())


def write_results(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def seed_standards(
    *,
    output_dir: Path,
    manifest_path: Path,
    results_path: Path,
    dry_run: bool,
) -> tuple[list[SourceCandidate], list[dict[str, str]]]:
    candidates: list[SourceCandidate] = []
    results: list[dict[str, str]] = []

    ingestion: IngestionService | None = None
    registry: SourceRegistryService | None = None
    if not dry_run:
        init_db()
        db_context = SessionLocal()
        ingestion = IngestionService(db_context, IngestionConfig())
        registry = SourceRegistryService(SourceRepository(db_context))
    else:
        db_context = None

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        for record in STANDARDS:
            file_name = sanitize_filename(f"{record.standard_no}_{record.title}", 150) + ".md"
            card_path = output_dir / file_name
            markdown = standard_markdown(record)
            import_result = None
            registry_status = "dry_run"
            candidate_status = "candidate" if dry_run else "collected"

            if not dry_run:
                card_path.write_text(markdown, encoding="utf-8")
                assert ingestion is not None
                assert registry is not None
                import_result = ingestion.import_document(
                    card_path,
                    title=f"{record.standard_no}《{record.title}》",
                    source_path=record.url,
                    file_name=card_path.name,
                    source_type="standard_document",
                )
                candidate_status = import_result.status
                candidate = candidate_from_standard(record, card_path, candidate_status)
                registry_result = registry.register_candidate(
                    candidate,
                    document_id=import_result.document_id,
                )
                registry_status = "created" if registry_result.created else "updated"
            else:
                candidate = candidate_from_standard(record, card_path, candidate_status)

            candidates.append(candidate)
            results.append(
                {
                    "source_id": record.source_id,
                    "standard_no": record.standard_no,
                    "title": record.title,
                    "status": candidate_status,
                    "document_id": str(import_result.document_id) if import_result else "",
                    "chunk_count": str(import_result.chunk_count) if import_result else "",
                    "card_path": str(card_path),
                    "registry_status": registry_status,
                }
            )

        if not dry_run:
            write_candidates_manifest(manifest_path, candidates)
            write_results(results_path, results)
    finally:
        if db_context is not None:
            db_context.close()

    return candidates, results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed metadata-only Chinese hydraulic/RFC standards into the local corpus."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/imports/chinese_standards_metadata"),
        help="Directory for generated metadata-only Markdown cards.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("data/corpus_expansion/chinese_standards_metadata.csv"),
        help="Source candidate manifest written after import.",
    )
    parser.add_argument(
        "--results",
        type=Path,
        default=Path("data/evaluation/stage40_chinese_standards_results.csv"),
        help="Import result CSV written after import.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned standards without writing files or importing into the database.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    candidates, results = seed_standards(
        output_dir=args.output_dir,
        manifest_path=args.manifest,
        results_path=args.results,
        dry_run=args.dry_run,
    )
    print(
        "chinese standards metadata seed\t"
        f"dry_run={args.dry_run}\t"
        f"records={len(candidates)}\t"
        f"imported={sum(1 for row in results if row['document_id'])}\t"
        f"output_dir={args.output_dir}"
    )
    for row in results:
        print(
            f"- {row['standard_no']} {row['title']}\t"
            f"status={row['status']}\t"
            f"document_id={row['document_id'] or 'n/a'}"
        )


if __name__ == "__main__":
    main()
