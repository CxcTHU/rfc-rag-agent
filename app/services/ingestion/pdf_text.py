"""阶段 18：PDF 文本结构化与解析加固。

pypdf 抽取出来的原始 PDF 文本是“扁平”的：没有 Markdown 标题层级、跨行断词、
表格按列对齐、夹杂页眉页脚和公式坐标噪声。本模块对原始文本做 deterministic 的
结构化后处理，让后续 cleaner/splitter 能拿到带 `#` 标题的文本，从而：

- chunk 能带上真实的 `heading_path`（属于哪一章节）。
- 表格行不被切碎，且可被检索识别。
- 跨行连字符断词（``concre-\nte`` -> ``concrete``）被合并。
- 重复页眉页脚、孤立页码和控制字符被清洗。

所有函数都是纯函数，不读文件、不联网，可用合成文本 fixture 测试。
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter


# 已知章节关键词（整行匹配，忽略大小写），命中即视为一级标题。
SECTION_KEYWORDS = {
    "abstract",
    "introduction",
    "background",
    "related work",
    "literature review",
    "materials and methods",
    "materials",
    "methods",
    "methodology",
    "experimental program",
    "experimental setup",
    "results",
    "results and discussion",
    "discussion",
    "conclusion",
    "conclusions",
    "conclusions and future work",
    "acknowledgment",
    "acknowledgments",
    "acknowledgements",
    "references",
    "nomenclature",
}

# 中文论文常见章节关键词（去空格后整行匹配）。不含中图分类号/收稿日期/作者简介等前言元数据。
CHINESE_SECTION_KEYWORDS = {
    "摘要",
    "关键词",
    "关键字",
    "引言",
    "前言",
    "绪论",
    "研究背景",
    "试验方案",
    "试验材料",
    "试验方法",
    "试验结果",
    "结果与分析",
    "结果与讨论",
    "讨论",
    "结论",
    "结语",
    "结束语",
    "参考文献",
    "致谢",
}

# 编号章节标题，例如 "1 Introduction" / "2.1. Methods" / "3.2.1 Results"。
NUMBERED_HEADING_RE = re.compile(
    r"^(?P<num>\d+(?:\.\d+)*)\.?\s+(?P<title>[^\d].{0,90})$"
)

# 中文数字章节标题，例如 "一、引言" / "（三）结论"。
# 必须带顿号/句点分隔或括号包裹，避免误匹配 "一是" / "一方面" / "一旦..." 这类正文。
CHINESE_NUM_HEADING_RE = re.compile(
    r"^(?:[（(](?P<n1>[一二三四五六七八九十百]+)[)）]|(?P<n2>[一二三四五六七八九十百]+)[、.．])\s*"
    r"(?P<title>[一-鿿].{0,40})$"
)

# 句末标点：标题一般不以这些结尾。
SENTENCE_END = ".。;；,，:：!！?？"

CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
MULTISPACE_RE = re.compile(r"[ \t]{2,}")


def structure_pdf_pages(pages: list[str]) -> str:
    """把多页 PDF 文本结构化成带 Markdown 标题的文本。

    会先跨页检测重复页眉页脚并去除，再逐页结构化，最后拼成
    ``## Page N`` 分块（保留旧行为，便于排查 chunk 所在页）。
    """

    normalized_pages = [normalize_unicode(page) for page in pages]
    repeated = detect_repeated_header_footer(normalized_pages)

    blocks: list[str] = []
    for index, page in enumerate(normalized_pages, start=1):
        page_body = structure_page_text(page, drop_lines=repeated)
        if not page_body.strip():
            continue
        blocks.append(f"## Page {index}\n\n{page_body}")
    return "\n\n".join(blocks)


def structure_page_text(text: str, drop_lines: set[str] | None = None) -> str:
    """对单页文本做结构化：去噪 -> 合并断词 -> 标题/表格识别。"""

    drop_lines = drop_lines or set()
    text = normalize_unicode(text)
    text = dehyphenate(text)

    raw_lines = text.split("\n")
    output: list[str] = []
    table_buffer: list[str] = []

    def flush_table() -> None:
        if not table_buffer:
            return
        rendered = render_table_block(table_buffer)
        if rendered:
            output.append(rendered)
        table_buffer.clear()

    for raw_line in raw_lines:
        line = MULTISPACE_RE.sub("  ", raw_line.rstrip())
        stripped = line.strip()

        if not stripped:
            flush_table()
            output.append("")
            continue

        if stripped in drop_lines or is_noise_line(stripped):
            continue

        if is_table_row(line):
            table_buffer.append(line)
            continue

        flush_table()

        heading = detect_heading(stripped)
        if heading is not None:
            level, title = heading
            output.append(f"{'#' * level} {title}")
        else:
            output.append(stripped)

    flush_table()

    # 合并多余空行。
    result = "\n".join(output)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


def normalize_unicode(text: str) -> str:
    """统一 unicode：折叠兼容字符、去控制符、统一各种横线为 ASCII 连字符。"""

    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = unicodedata.normalize("NFKC", text)
    text = CONTROL_CHARS_RE.sub("", text)
    # 统一各种 dash/minus 到 ASCII '-'，避免连字符判断失败。
    for dash in ("‐", "‑", "‒", "–", "—", "−"):
        text = text.replace(dash, "-")
    return text


def dehyphenate(text: str) -> str:
    """合并行尾连字符断词：``concre-\nte`` -> ``concrete``。

    仅在“连字符前是小写字母、换行后首字符是小写字母”时合并，避免误并
    复合词（如 ``rock-\nfilled`` 中 filled 是小写也合并，这是期望行为）和
    真正的破折号列表。
    """

    def _join(match: re.Match[str]) -> str:
        return match.group(1) + match.group(2)

    return re.sub(r"([A-Za-z一-鿿])-\n([a-z一-鿿])", _join, text)


def detect_heading(line: str) -> tuple[int, str] | None:
    """识别标题行，返回 ``(level, title)``；不是标题返回 ``None``。

    保守策略，只升级高置信度标题：
    - 已知章节关键词（Abstract/Introduction/References...）-> level 1。
    - 编号章节（``2.1 Methods``）-> level = 点分段数。
    - 短全大写行（<=6 个词、字母为主）-> level 1。
    """

    lowered = line.lower().strip(" .:")
    if lowered in SECTION_KEYWORDS:
        return 1, line.strip()

    # 中文章节关键词（去掉内部空格和尾部标点后整行匹配，如 "摘 要"、"关键词："）。
    compact_cn = re.sub(r"\s+", "", line).strip(" .:：、，。")
    if compact_cn in CHINESE_SECTION_KEYWORDS:
        return 1, line.strip()

    # 中文数字章节标题，如 "一、引言"。
    cn_match = CHINESE_NUM_HEADING_RE.match(line)
    if cn_match:
        title = cn_match.group("title").strip()
        if title and title[-1] not in SENTENCE_END:
            return 1, line.strip()

    match = NUMBERED_HEADING_RE.match(line)
    if match:
        title = match.group("title").strip()
        num = match.group("num")
        first = title[:1]
        looks_like_word = first.isalpha() or ("一" <= first <= "鿿")
        has_formula_noise = any(ch in title for ch in "()=_[]{}|<>\\")
        # 章节号一般较小；过大（如 "150 m"、"2009"）多是测量值或年份。
        try:
            num_too_large = int(num.split(".")[0]) > 40
        except ValueError:
            num_too_large = True
        # 标题含数字多半是测量值/表格行（如 "9 DA M 0 + 251"、"1 ... 2009 233 660"）。
        title_has_digit = bool(re.search(r"\d", title))
        # 标题必须含真正的词：>=2 个连续中文，或 >=3 个连续 ASCII 字母。
        has_real_word = bool(
            re.search(r"[一-鿿]{2,}", title) or re.search(r"[A-Za-z]{3,}", title)
        )
        if (
            title
            and looks_like_word
            and not has_formula_noise
            and not num_too_large
            and not title_has_digit
            and has_real_word
            and title[-1] not in SENTENCE_END
            and len(title) <= 80
        ):
            level = num.count(".") + 1
            return min(level, 6), f"{num} {title}".strip()
        return None

    if is_all_caps_heading(line):
        return 1, line.strip()

    return None


def is_all_caps_heading(line: str) -> bool:
    stripped = line.strip()
    letters = [ch for ch in stripped if ch.isalpha()]
    if len(letters) < 3:
        return False
    if any("一" <= ch <= "鿿" for ch in stripped):
        return False  # 中文不用全大写判断
    # 只允许字母和空格组成的行；公式/符号片段（SCC/SCM、C_III）不算标题。
    if not all(ch.isalpha() or ch.isspace() for ch in stripped):
        return False
    words = stripped.split()
    # 要求多词标题，避免把单个缩写（SCC、ITZ）误判成标题。
    if not (2 <= len(words) <= 6):
        return False
    # 拒绝被空格拆成单字母的碎片（中文论文里的图注/公式残渣，如 "D A M"、"DO I"、"G DP"）。
    if any(len(word) < 2 for word in words):
        return False
    if stripped[-1] in SENTENCE_END:
        return False
    upper = [ch for ch in letters if ch.isupper()]
    return len(upper) / len(letters) >= 0.85


def is_table_row(line: str) -> bool:
    """识别表格行：被 2+ 空格分隔出 >=3 列，且至少一列含数字。"""

    if "  " not in line:
        return False
    cells = [cell for cell in re.split(r" {2,}", line.strip()) if cell]
    if len(cells) < 3:
        return False
    has_number = any(re.search(r"\d", cell) for cell in cells)
    return has_number


def render_table_block(rows: list[str]) -> str:
    """把连续表格行渲染成可检索的管线分隔块，并标注为表格。"""

    rendered_rows: list[str] = []
    for row in rows:
        cells = [cell.strip() for cell in re.split(r" {2,}", row.strip()) if cell.strip()]
        if cells:
            rendered_rows.append(" | ".join(cells))
    if not rendered_rows:
        return ""
    body = "\n".join(rendered_rows)
    return f"[表格]\n{body}"


def is_noise_line(line: str) -> bool:
    """识别孤立噪声行：纯页码、纯符号、坐标残渣。"""

    stripped = line.strip()
    if not stripped:
        return False
    # 纯数字短行（孤立页码）。
    if re.fullmatch(r"\d{1,4}", stripped):
        return True
    # 没有任何字母/数字（纯标点/符号噪声）。
    if not re.search(r"[A-Za-z0-9一-鿿]", stripped):
        return True
    return False


def detect_repeated_header_footer(pages: list[str]) -> set[str]:
    """跨页找重复出现的短行（页眉页脚），返回应删除的行集合。

    规则：某条 <=80 字符、非标题样式的短行，在至少一半（且 >=2）页面出现，
    视为页眉页脚噪声。
    """

    if len(pages) < 3:
        return set()

    counter: Counter[str] = Counter()
    for page in pages:
        seen_on_page: set[str] = set()
        for raw_line in page.split("\n"):
            stripped = raw_line.strip()
            if not stripped or len(stripped) > 80:
                continue
            if stripped in seen_on_page:
                continue
            seen_on_page.add(stripped)
            counter[stripped] += 1

    threshold = max(2, len(pages) // 2)
    repeated = {
        line
        for line, count in counter.items()
        if count >= threshold and detect_heading(line) is None
    }
    return repeated
