---
stage: "阶段 1"
phase: "Phase 2"
status: "已完成"
---

# 阶段 1 Phase 2 - 文本解析清洗与切分

所属阶段：[[阶段 1 - 本地资料导入与关键词检索]]
所属汇报索引：[[阶段 1 Phase 汇报索引]]

## 1. 本 Phase 目标

把 Markdown/TXT 文件读成干净文本，并切成后续可以检索和引用的 chunk。

## 2. 本 Phase 完成的主要任务

- 新增 `app/services/ingestion/parser.py`。
- 新增 `app/services/ingestion/cleaner.py`。
- 新增 `app/services/ingestion/splitter.py`。
- 支持从 Markdown 标题推断资料标题。
- chunk 记录 `chunk_index`、`char_count`、`heading_path`、`start_char`、`end_char`。
- 新增 parser、cleaner、splitter 对应测试。

## 3. 新增/修改了哪些内容

- 新增 `tests/test_ingestion_parser.py`。
- 新增 `tests/test_ingestion_cleaner.py`。
- 新增 `tests/test_ingestion_splitter.py`。
- 新增 `app/services/ingestion/` 目录。

## 4. 关键代码或模块说明

- parser 负责读取文件并抽取原始文本。
- cleaner 负责去掉 BOM、空字符、多余空白和异常换行。
- splitter 负责把长文本按标题、段落和字符长度切成 chunk。

## 5. 遇到的问题与解决方式

问题：如果 chunk 太长，检索结果不精确；如果太短，又会丢失上下文。

解决方式：阶段 1 先使用字符长度、标题路径和 overlap 的组合策略，并保留真实资料微调空间。

## 6. 新词解释

- parser：解析器，把文件读成程序能处理的文本。
- cleaner：清洗器，去掉噪声字符和多余空白。
- splitter：切分器，把长文本切成小段。
- chunk：可被检索和引用的资料片段，例如堆石混凝土论文中的一段施工质量说明。

## 7. 验证结果

- parser、cleaner、splitter 单元测试通过。
- Markdown/TXT 可以被读取、清洗和切分。

## 8. 当前遗留问题

- 还没有把切出来的 chunk 保存进数据库。
- 还没有处理真实资料卡中的 metadata 噪声。

## 9. 下一 Phase 要做什么

进入 Phase 3，实现 repository 和 ingestion service，把解析、清洗、切分、保存串起来。

## 10. 面试表达

“我把资料处理拆成 parser、cleaner、splitter 三步，每一步职责单一、可以单测。这样后续如果 PDF 解析、OCR 或 chunk 策略变化，只需要替换对应模块，不会影响数据库和 API 层。”
