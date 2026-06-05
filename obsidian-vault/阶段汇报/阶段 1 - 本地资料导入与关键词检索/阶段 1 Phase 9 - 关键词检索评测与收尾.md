---
stage: "阶段 1"
phase: "Phase 9"
status: "已完成"
---

# 阶段 1 Phase 9 - 关键词检索评测与收尾

所属阶段：[[阶段 1 - 本地资料导入与关键词检索]]
所属汇报索引：[[阶段 1 Phase 汇报索引]]

## 1. 本 Phase 目标

建立关键词检索评测基线，并完成阶段 1 的文档校准、提交、合并和远程推送。

## 2. 本 Phase 完成的主要任务

- 新增 `data/evaluation/keyword_queries.csv`。
- 新增 `scripts/evaluate_keyword_search.py`。
- 初次评测 11/15 通过。
- 根据失败案例微调关键词检索。
- 增加中英文同义词扩展、具体词加权、领域泛词降权、命中次数上限和来源均衡。
- `POST /search` 返回 `source_type`。
- 更新关键词检索测试。
- 阶段 1 最终评测 15/15 通过。
- 将阶段 1 合并到 `main`，并校准 README、AGENT、progress 和 Obsidian。

## 3. 新增/修改了哪些内容

- 新增 `data/evaluation/keyword_queries.csv`。
- 新增 `data/evaluation/keyword_results.csv`。
- 新增 `scripts/evaluate_keyword_search.py`。
- 修改 `app/services/retrieval/keyword_search.py`。
- 修改 `app/schemas/search.py`。
- 修改 `app/api/search.py`。
- 修改 `tests/test_keyword_search.py`。
- 修改 `README.md`、`docs/progress.md`、`AGENT.MD` 和 Obsidian 阶段页/索引。

## 4. 关键代码或模块说明

- `KeywordSearchService` 负责查询词扩展、chunk 评分、来源均衡和结果排序。
- `SearchTerm` 让每个查询词携带权重和“是否具体词”的标记。
- `evaluate_keyword_search.py` 自动运行评测集并输出命中排名、来源类型和 metadata 比例。

## 5. 遇到的问题与解决方式

问题：`弹性模量` 无法稳定召回 `elastic modulus`，`peridynamics` 容易被泛词淹没，`metadata_record` 容易刷屏。

解决方式：加入中英文同义词、具体词加权、泛词降权、命中次数裁剪和 metadata 来源占比控制。

## 6. 新词解释

- baseline：基线，用来作为后续优化对照的第一版稳定结果。
- query expansion：查询扩展，例如把“弹性模量”扩成 `elastic modulus`。
- 泛词降权：降低 `concrete`、`dam` 这类太常见词的影响。
- metadata_ratio：检索结果中题录卡片占比，用来观察 metadata_record 是否过度刷屏。

## 7. 验证结果

- `scripts/evaluate_keyword_search.py`：15/15 通过。
- `metadata_ratio` 最高控制在 0.50。
- `python -m pytest tests\test_keyword_search.py tests\test_search_api.py -q`：6 个测试通过。
- `python -m pytest`：38 个测试通过。
- `python -m py_compile scripts\evaluate_keyword_search.py app\services\retrieval\keyword_search.py app\schemas\search.py app\api\search.py`：通过。

## 8. 当前遗留问题

- 关键词检索不能理解真正语义，只能作为阶段 2 向量检索的 baseline。
- 题录元数据仍保存在 `documents/chunks`，后续阶段 4 需要 source registry。
- 尚未实现引用式问答和大模型调用。

## 9. 下一 Phase 要做什么

阶段 1 已完成。下一大阶段进入 [[阶段 2 - Embedding 与向量检索]]，实现问题和 chunk 的向量化语义召回。

## 10. 面试表达

“阶段 1 我不只是实现了关键词检索，还建立了评测基线。通过 15 个代表性查询，我发现中文英文、同义词、泛词和 metadata 来源都会影响结果质量，于是加入同义词扩展、具体词加权、泛词降权和来源均衡。最终关键词评测 15/15 通过，为阶段 2 的向量检索提供了清晰对照。”
