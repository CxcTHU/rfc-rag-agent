import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Chunk, Document


@dataclass(frozen=True)
class KeywordSearchResult:
    document_id: int
    document_title: str
    source_type: str
    source_path: str | None
    file_name: str
    chunk_id: int
    chunk_index: int
    content: str
    heading_path: str | None
    score: float
    chunk_type: str = "text"
    source_image_path: str | None = None


@dataclass(frozen=True)
class SearchTerm:
    text: str
    weight: float
    specific: bool = True


class KeywordSearchService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def search(self, query: str, top_k: int = 5) -> list[KeywordSearchResult]:
        terms = expand_query_terms(query)
        if not terms:
            raise ValueError("query must not be empty")
        if top_k <= 0:
            raise ValueError("top_k must be greater than 0")

        statement = select(Chunk, Document).join(Document, Chunk.document_id == Document.id)
        rows = self.db.execute(statement).all()

        results: list[KeywordSearchResult] = []
        for chunk, document in rows:
            score = score_match(
                query=query,
                terms=terms,
                title=document.title,
                content=chunk.content,
                heading_path=chunk.heading_path,
            )
            if score <= 0:
                continue

            results.append(
                KeywordSearchResult(
                    document_id=document.id,
                    document_title=document.title,
                    source_type=document.source_type,
                    source_path=document.source_path,
                    file_name=document.file_name,
                    chunk_id=chunk.id,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    heading_path=chunk.heading_path,
                    score=score,
                    chunk_type=chunk.chunk_type,
                    source_image_path=chunk.source_image_path,
                )
            )

        sorted_results = sorted(
            results,
            key=lambda item: (-item.score, source_type_rank(item.source_type), item.document_id, item.chunk_index),
        )
        return diversify_results(sorted_results, top_k)


def extract_terms(query: str) -> list[str]:
    stripped = query.strip()
    if not stripped:
        return []

    terms = [term for term in re.split(r"\s+", stripped) if term]
    if len(terms) == 1:
        return terms

    return list(dict.fromkeys([stripped, *terms]))


DOMAIN_GENERIC_TERMS = {
    "concrete",
    "dam",
    "rock-filled",
    "rock-fill",
    "rock",
    "filled",
    "self-compacting",
    "堆石混凝土",
    "混凝土",
    "大坝",
}

SYNONYM_RULES = [
    (["堆石混凝土"], [("rock-filled concrete", 1.2), ("rock filled concrete", 1.2), ("rock-fill concrete", 1.2), ("rfc", 0.8)]),
    (["rock-filled concrete", "rock filled concrete", "rock-fill concrete"], [("堆石混凝土", 1.2), ("rfc", 0.8)]),
    (["rcc", "roller-compacted concrete", "rolled concrete"], [("roller-compacted concrete", 2.0), ("rolled concrete", 1.6), ("rollcrete", 1.4)]),
    (["自密实"], [("self-compacting", 1.3), ("self compacting", 1.3), ("self-consolidating", 1.0), ("scc", 0.8)]),
    (["self-compacting", "self compacting", "self-consolidating"], [("自密实", 1.3), ("scc", 0.8)]),
    (["填充能力", "充填", "填充"], [("filling capacity", 1.8), ("filling performance", 1.4), ("compactness", 1.1), ("prepacked rock", 1.1)]),
    (["filling capacity", "filling performance"], [("填充能力", 1.8), ("充填", 1.2), ("填充", 1.2)]),
    (["施工质量", "质量控制"], [("quality control", 1.9), ("construction quality", 1.6), ("instrumentation", 1.4), ("compaction detection", 1.5), ("compactness", 1.2)]),
    (["quality control", "construction quality"], [("施工质量", 1.7), ("质量控制", 1.7), ("密实度", 1.0)]),
    (["密实度"], [("compactness", 1.7), ("compaction", 1.4), ("compaction detection", 1.5)]),
    (["灌满", "灌实", "填满"], [("compactness", 1.4), ("compaction detection", 1.3), ("filling process", 1.3)]),
    (["现场", "判断"], [("on-site", 1.1), ("on-site experiment", 1.2), ("compaction detection", 1.1)]),
    (["检测"], [("detection", 1.3), ("instrumentation", 1.1), ("monitoring", 1.1)]),
    (["水化热", "温升", "温控"], [("hydration heat", 1.8), ("adiabatic temperature rise", 1.8), ("temperature", 1.3), ("thermal", 1.2)]),
    (["temperature", "thermal", "hydration heat"], [("温升", 1.2), ("温控", 1.2), ("水化热", 1.4)]),
    (["弹性模量"], [("elastic modulus", 2.0), ("mechanical properties", 1.2)]),
    (["elastic modulus"], [("弹性模量", 2.0)]),
    (["力学", "强度", "抗压"], [("mechanical", 1.3), ("strength", 1.3), ("compressive", 1.3)]),
    (["抗压表现", "抗压行为"], [("compressive behavior", 1.7), ("compressive strength", 1.5)]),
    (["抗震", "地震"], [("seismic", 1.8), ("earthquake", 1.5)]),
    (["seismic", "earthquake"], [("抗震", 1.6), ("地震", 1.4)]),
    (["综述"], [("review", 1.8), ("prospects", 1.3), ("state-of-the-art", 1.3)]),
    (["细观", "细观模拟"], [("mesoscopic", 2.0), ("mesoscale", 1.8), ("meso-scale", 1.8)]),
    (["数值", "模拟"], [("simulation", 1.5), ("numerical", 1.5), ("finite element", 1.2)]),
    (["mesoscopic", "mesoscale", "meso-scale"], [("细观", 1.8), ("细观模拟", 1.8)]),
    (["界面", "接触界面"], [("interface", 1.5), ("interfacial", 1.5), ("interfacial transition zone", 1.5), ("itz", 1.4)]),
    (["itz", "interfacial transition zone", "interface"], [("界面", 1.4), ("接触界面", 1.2)]),
    (["徐变", "长期变形"], [("creep", 2.0), ("creep behaviour", 1.8), ("long-term deformation", 1.5)]),
    (["creep", "creep behaviour", "long-term deformation"], [("徐变", 1.8), ("长期变形", 1.5)]),
    (["冻融", "抗冻"], [("freeze-thaw", 2.0), ("freeze thaw", 2.0), ("freeze-thaw resistence", 1.6), ("impermeability", 1.2), ("durability", 1.1)]),
    (["freeze-thaw", "freeze thaw"], [("冻融", 1.8), ("抗冻", 1.6), ("impermeability", 1.2)]),
    (["孔隙率", "孔洞", "孔隙"], [("porosity", 2.0), ("void", 1.8), ("pores", 1.5), ("aperture", 1.3), ("defects", 1.1)]),
    (["porosity", "void", "pores", "aperture"], [("孔隙率", 1.8), ("孔洞", 1.5), ("孔隙", 1.5)]),
    (["碳排放", "排放", "成本", "工期"], [("emission", 1.8), ("cost", 1.7), ("schedule", 1.7), ("life-cycle", 1.4), ("life cycle", 1.4), ("lca", 1.1)]),
    (["emission", "cost", "schedule", "life-cycle", "life cycle"], [("碳排放", 1.5), ("成本", 1.4), ("工期", 1.4)]),
    (["钢纤维"], [("steel fiber", 2.0), ("steel fibre", 2.0), ("steel fiber-reinforced", 1.8)]),
    (["steel fiber", "steel fibre"], [("钢纤维", 1.8)]),
    (["冷缝"], [("cold joint", 1.8), ("cold joints", 1.8)]),
    (["层间"], [("interlayer", 1.5), ("between layers", 1.2)]),
    (["剪切"], [("shear", 1.8)]),
    (["剪力键", "岩石剪力键"], [("rock shear keys", 2.0), ("shear keys", 1.8)]),
    (["rock shear keys", "shear keys"], [("剪力键", 1.8), ("岩石剪力键", 1.8)]),
    (["坝型"], [("dam type", 1.6), ("gravity dam", 1.2), ("arch dam", 1.2)]),
    (["peridynamics"], [("peridynamics", 3.0)]),
]


def expand_query_terms(query: str) -> list[SearchTerm]:
    raw_terms = extract_terms(query)
    if not raw_terms:
        return []

    expanded: dict[str, SearchTerm] = {}
    multiple_terms = len(raw_terms) > 1
    for term in raw_terms:
        normalized = normalize_text(term)
        if not normalized:
            continue
        generic = multiple_terms and normalized in DOMAIN_GENERIC_TERMS
        weight = 0.35 if generic else original_term_weight(normalized)
        add_search_term(expanded, normalized, weight=weight, specific=not generic)

    normalized_query = normalize_text(query)
    for triggers, additions in SYNONYM_RULES:
        if any(normalize_text(trigger) in normalized_query for trigger in triggers):
            for synonym, weight in additions:
                add_search_term(expanded, normalize_text(synonym), weight=weight, specific=True)

    return list(expanded.values())


def add_search_term(
    terms: dict[str, SearchTerm],
    text: str,
    weight: float,
    specific: bool,
) -> None:
    existing = terms.get(text)
    if existing is None or weight > existing.weight:
        terms[text] = SearchTerm(text=text, weight=weight, specific=specific or (existing.specific if existing else False))


def original_term_weight(term: str) -> float:
    if len(term) >= 10 or re.search(r"[^\w\s-]", term):
        return 1.4
    if term in {"rfc", "scc", "dem"}:
        return 1.2
    return 1.0


def normalize_text(text: str | None) -> str:
    normalized = (text or "").casefold()
    return normalized.translate(
        str.maketrans(
            {
                "ﬁ": "fi",
                "ﬂ": "fl",
                "‐": "-",
                "‑": "-",
                "‒": "-",
                "–": "-",
                "—": "-",
            }
        )
    )


def score_match(
    query: str,
    terms: list[SearchTerm],
    title: str,
    content: str,
    heading_path: str | None,
) -> float:
    normalized_query = normalize_text(query.strip())
    normalized_title = normalize_text(title)
    normalized_content = normalize_text(content)
    normalized_heading = normalize_text(heading_path)

    score = 0.0
    chunk_score = 0.0
    title_score = 0.0
    specific_hit = False
    for term in terms:
        normalized_term = normalize_text(term.text)
        if not normalized_term:
            continue
        content_hits = capped_count(normalized_content, normalized_term)
        heading_hits = capped_count(normalized_heading, normalized_term)
        title_hits = capped_count(normalized_title, normalized_term)
        if term.specific and (content_hits or heading_hits or title_hits):
            specific_hit = True
        chunk_score += content_hits * term.weight * 1.0
        chunk_score += heading_hits * term.weight * 1.5
        title_score += title_hits * term.weight * 3.0

    if normalized_query and normalized_query in normalized_content:
        chunk_score += 2.0
    if normalized_query and normalized_query in normalized_heading:
        chunk_score += 2.5
    if chunk_score > 0 and normalized_query and normalized_query in normalized_title:
        title_score += 5.0

    has_specific_terms = any(term.specific for term in terms)
    if has_specific_terms and not specific_hit:
        return 0.0
    if chunk_score <= 0:
        return 0.0

    score = chunk_score + title_score
    return score


def capped_count(text: str, term: str, cap: int = 5) -> int:
    if not text or not term:
        return 0
    return min(text.count(term), cap)


def source_type_rank(source_type: str) -> int:
    ranks = {
        "local_file": 0,
        "institutional_access_pdf": 1,
        "open_access_pdf": 2,
        "web_page": 3,
        "wikipedia": 3,
        "standard_document": 3,
        "metadata_record": 4,
    }
    return ranks.get(source_type, 5)


def diversify_results(
    results: list[KeywordSearchResult],
    top_k: int,
) -> list[KeywordSearchResult]:
    if len(results) <= top_k:
        return results

    metadata_limit = max(1, int(top_k * 0.6))
    selected: list[KeywordSearchResult] = []
    deferred: list[KeywordSearchResult] = []
    selected_documents: set[int] = set()
    metadata_count = 0

    for result in results:
        if len(selected) >= top_k:
            deferred.append(result)
            continue
        if result.document_id in selected_documents:
            deferred.append(result)
            continue
        if result.source_type == "metadata_record" and metadata_count >= metadata_limit:
            deferred.append(result)
            continue

        selected.append(result)
        selected_documents.add(result.document_id)
        if result.source_type == "metadata_record":
            metadata_count += 1

    for result in deferred:
        if len(selected) >= top_k:
            break
        selected.append(result)

    return selected
