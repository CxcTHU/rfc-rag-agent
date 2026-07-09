from __future__ import annotations

from collections.abc import Sequence

from app.services.table_rag.models import StructuredTableDraft, TableRetrievalUnitDraft
from app.services.table_rag.normalization import content_hash, short_preview


UNIT_TYPES = {
    "table_summary",
    "table_schema",
    "row_pack",
    "column_pack",
    "cell_fact",
    "caption_context",
}


def build_retrieval_units(table: StructuredTableDraft) -> list[TableRetrievalUnitDraft]:
    units: list[TableRetrievalUnitDraft] = []
    units.append(table_summary_unit(table))
    units.append(table_schema_unit(table))
    if table.caption or table.header_text:
        units.append(caption_context_unit(table))
    units.extend(row_pack_units(table))
    units.extend(column_pack_units(table))
    units.extend(cell_fact_units(table))
    return [with_hash(unit) for unit in units if unit.text.strip()]


def table_summary_unit(table: StructuredTableDraft) -> TableRetrievalUnitDraft:
    topic = table.caption or table.header_text or f"第 {table.page_number or '?'} 页表格"
    main_rows = first_column_values(table.normalized_rows[1:], limit=12)
    text = (
        f"表格摘要：该表位于第 {table.page_number or '?'} 页，主题为{topic}。\n"
        f"主要列：{join_values(table.headers)}。\n"
        f"主要行：{join_values(main_rows)}。\n"
        "可回答问题：表格主题、字段含义、行列定位、数值提取、单位对比。"
    )
    return TableRetrievalUnitDraft(
        unit_type="table_summary",
        unit_index=0,
        text=text,
        metadata={
            "topic": topic,
            "page": table.page_number,
            "entities": main_rows,
            "measures": list(table.headers),
            "units": sorted(set(table.units.values())),
            "query_intents": ["表格", "行列查询", "数值提取", "单位对比"],
        },
    )


def table_schema_unit(table: StructuredTableDraft) -> TableRetrievalUnitDraft:
    parts: list[str] = []
    for index, header in enumerate(table.headers):
        unit = table.units.get(str(index))
        parts.append(f"{index + 1}. {header}" + (f" ({unit})" if unit else ""))
    return TableRetrievalUnitDraft(
        unit_type="table_schema",
        unit_index=0,
        text="表格字段：\n" + "\n".join(parts),
        metadata={"headers": list(table.headers), "units": table.units},
    )


def caption_context_unit(table: StructuredTableDraft) -> TableRetrievalUnitDraft:
    text = f"表格上下文：第 {table.page_number or '?'} 页。标题/邻近文本：{table.caption or table.header_text or ''}"
    return TableRetrievalUnitDraft(
        unit_type="caption_context",
        unit_index=0,
        text=text,
        metadata={"caption": table.caption, "header_text": table.header_text, "page": table.page_number},
    )


def row_pack_units(table: StructuredTableDraft) -> list[TableRetrievalUnitDraft]:
    units: list[TableRetrievalUnitDraft] = []
    for row_index, row in enumerate(table.normalized_rows[1:], start=1):
        row_text = row_to_text(table.headers, row)
        if not row_text:
            continue
        units.append(
            TableRetrievalUnitDraft(
                unit_type="row_pack",
                unit_index=row_index,
                text=f"表格第 {row_index} 行：{row_text}",
                metadata={"row_index": row_index, "headers": list(table.headers)},
                source_row_index=row_index,
            )
        )
    return units


def column_pack_units(table: StructuredTableDraft, *, value_limit: int = 12) -> list[TableRetrievalUnitDraft]:
    units: list[TableRetrievalUnitDraft] = []
    for col_index, header in enumerate(table.headers):
        values = [
            row[col_index]
            for row in table.normalized_rows[1:]
            if col_index < len(row) and row[col_index].strip()
        ][:value_limit]
        unit = table.units.get(str(col_index))
        text = f"表格列：{header}" + (f"；单位：{unit}" if unit else "")
        if values:
            text += f"；主要取值：{join_values(values)}"
        units.append(
            TableRetrievalUnitDraft(
                unit_type="column_pack",
                unit_index=col_index,
                text=text,
                metadata={"column_index": col_index, "header": header, "unit": unit, "value_count": len(values)},
                source_col_index=col_index,
            )
        )
    return units


def cell_fact_units(table: StructuredTableDraft) -> list[TableRetrievalUnitDraft]:
    units: list[TableRetrievalUnitDraft] = []
    unit_index = 0
    for row_index, row in enumerate(table.normalized_rows[1:], start=1):
        row_label = row[0] if row else ""
        for col_index, value in enumerate(row):
            if not value.strip():
                continue
            header = table.headers[col_index] if col_index < len(table.headers) else f"列{col_index + 1}"
            text = f"单元格事实：第 {row_index} 行 {row_label}，{header} = {value}"
            units.append(
                TableRetrievalUnitDraft(
                    unit_type="cell_fact",
                    unit_index=unit_index,
                    text=text,
                    metadata={
                        "row_index": row_index,
                        "column_index": col_index,
                        "row_label": row_label,
                        "header": header,
                    },
                    source_row_index=row_index,
                    source_col_index=col_index,
                )
            )
            unit_index += 1
    return units


def with_hash(unit: TableRetrievalUnitDraft) -> TableRetrievalUnitDraft:
    if unit.content_hash:
        return unit
    return TableRetrievalUnitDraft(
        unit_type=unit.unit_type,
        unit_index=unit.unit_index,
        text=unit.text,
        metadata=unit.metadata,
        source_row_index=unit.source_row_index,
        source_col_index=unit.source_col_index,
        content_hash=content_hash(unit.text),
    )


def first_column_values(rows: Sequence[Sequence[str]], *, limit: int) -> list[str]:
    values: list[str] = []
    for row in rows:
        if row and row[0].strip() and row[0].strip() not in values:
            values.append(short_preview(row[0].strip(), 40))
        if len(values) >= limit:
            break
    return values


def row_to_text(headers: Sequence[str], row: Sequence[str]) -> str:
    parts: list[str] = []
    for index, value in enumerate(row):
        if not value.strip():
            continue
        header = headers[index] if index < len(headers) else f"列{index + 1}"
        parts.append(f"{header}: {value}")
    return "；".join(parts)


def join_values(values: Sequence[str]) -> str:
    cleaned = [short_preview(value, 60) for value in values if value]
    return "、".join(cleaned) if cleaned else "无"
