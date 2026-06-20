# Subagent D — Goal Prompt：用户反馈闭环

请为本线程设置一个 goal：

按照当前项目的 AGENT.MD、README.md、docs/progress.md、docs/architecture.md，以及阶段 47 的 task_plan.md，在主 agent 完成 Phase 0-2 共享基础设施后的公共基线上，完成 **Track D：用户反馈闭环（反馈收集 + 评测集自增长）** 的开发与测试，并停在可交付状态。

目标分支建议为（从主 agent 的 phase-47 基线创建 worktree）：

codex/phase-47-track-d-feedback-loop

## 执行要求

1. 首先修改当前对话线程名称为：阶段47-TrackD-反馈闭环。
2. 先阅读 AGENT.MD、README.md、docs/progress.md、docs/architecture.md、task_plan.md、findings.md、progress.md。
3. 确认当前基线已包含 Phase 1-2 的共享基础设施：
   - Alembic 迁移 `0005` 中 `qa_feedback` 表
   - `app/db/models.py` 中 `QAFeedback` 模型
   - `app/schemas/feedback.py` 中 `FeedbackCreateRequest` / `FeedbackResponse`
   - `app/db/feedback_repository.py` 中 `FeedbackRepository`
   - `app/api/feedback.py` 中 `POST /feedback` / `GET /feedback/stats` 路由
4. **不修改共享文件**：不得直接修改 `alembic/versions/`、`app/db/models.py`、`app/schemas/agent.py`、`app/schemas/feedback.py`、`app/db/feedback_repository.py`、`app/api/feedback.py`、`app/frontend/static/app.js`、`app/api/agent.py`、`README.md`、`docs/progress.md`、`docs/architecture.md`。这些文件由主 agent 统一管理。
5. 可以创建分支和提交，但阶段完成后不要 git push；等待主 agent review 和 merge。

## 背景

当前系统的评测集（`data/evaluation/` 下的 CSV 文件）是手动维护的。用户每天与系统交互产生的 QA 对中，存在大量可用于评测的真实场景问答。本 Track 的目标是：让用户通过简单的 👍/👎 反馈标记回答质量，系统自动将高质量 QA 对导入评测集，形成评测数据的持续增长闭环。

## 核心交付

### 1. 反馈服务 `app/services/feedback/feedback_service.py`

核心逻辑：

```python
class FeedbackService:
    """反馈收集与处理服务"""

    def __init__(self, db: Session, repository: FeedbackRepository):
        self.db = db
        self.repo = repository

    def submit_feedback(
        self,
        question: str,
        answer: str,
        rating: str,            # "positive" | "negative"
        reason: str | None,     # 负反馈原因分类
        comment: str | None,    # 用户自由评论
        conversation_id: int | None = None,
        message_id: int | None = None,
        question_answer_log_id: int | None = None,
    ) -> QAFeedback:
        """提交一条反馈"""

    def get_positive_feedback_for_export(
        self,
        min_answer_length: int = 50,
        since_days: int | None = None,
    ) -> list[QAFeedback]:
        """获取可导出为评测集的正面反馈"""

    def get_feedback_stats(self) -> FeedbackStats:
        """返回反馈统计"""
```

负反馈 `reason` 枚举值：
- `"irrelevant"` — 答案与问题无关
- `"inaccurate"` — 答案包含错误信息
- `"incomplete"` — 答案不完整，缺少关键信息
- `"no_citation"` — 答案缺少引用来源
- `"wrong_citation"` — 引用的来源不正确
- `"other"` — 其他

`FeedbackStats` dataclass：

```python
@dataclass
class FeedbackStats:
    total: int
    positive: int
    negative: int
    positive_rate: float
    top_negative_reasons: list[tuple[str, int]]   # [(reason, count), ...]
    recent_7d_total: int
    recent_7d_positive_rate: float
    exportable_count: int                          # 可导出为评测集的数量
```

### 2. 评测集导出脚本 `scripts/export_phase47_feedback_to_eval.py`

核心逻辑：
- 从 `qa_feedback` 表中提取 `rating='positive'` 的记录
- 过滤条件：
  - `answer` 长度 >= 50 字符（过短的回答不入评测集）
  - 每个 `question` 只保留最新一条正面反馈（去重）
  - 不包含 API key、token 等敏感信息（正则扫描）
- 导出为 CSV 格式，字段对齐现有评测集结构：

```csv
query_id,question,expected_answer_keywords,difficulty,category,source
feedback_001,"水泥用量标准是多少？","水泥,用量,标准",medium,配合比,user_feedback
```

- `query_id` 前缀为 `feedback_` 以区分手动评测集
- `expected_answer_keywords` 从正面反馈的 `answer` 中自动提取（取 TF-IDF 前 5 个关键词）
- `category` 根据 `question` 自动分类（简单规则匹配：含"裂缝"→结构缺陷，含"配合比"→配合比，含"强度"→力学性能，其余→通用）
- 输出到 `data/evaluation/phase47_user_feedback_eval.csv`

参数：
- `--dry-run`：只统计不写入
- `--since-days N`：只导出最近 N 天的反馈
- `--min-length N`：最短回答长度过滤

### 3. 关键词提取工具 `app/services/feedback/keyword_extractor.py`

简单的中文关键词提取（不引入 jieba 等重依赖）：

```python
def extract_keywords(text: str, top_k: int = 5) -> list[str]:
    """从文本中提取关键词，用于生成 expected_answer_keywords"""
```

策略：
- 使用正则分词（按标点、空格、常见停用词切分）
- 按词频排序，取 top_k
- 过滤单字和常见停用词（"的"、"是"、"在"、"了"等）

### 4. 反馈 API 增强 — 追加到现有路由

主 agent 在 Phase 2 已创建了 `app/api/feedback.py` 的基础路由。本 Track 需要确认这些路由与 `FeedbackService` 正确对接。如果基础路由只是骨架（raise NotImplementedError），则在 `FeedbackService` 中实现完整逻辑，让路由调用 service 方法。

新增一个独立的导出路由文件 `app/api/feedback_export.py`：

```python
@router.get("/feedback/export")
async def export_feedback_to_eval(
    since_days: int | None = None,
    min_length: int = 50,
    dry_run: bool = False,
):
    """将正面反馈导出为评测集 CSV（供管理员使用）"""
```

### 5. 测试覆盖

- `tests/test_feedback_service.py`：
  - 提交正面反馈 → 数据库有记录
  - 提交负面反馈 + reason → 数据库有记录
  - get_feedback_stats() → 统计正确
  - get_positive_feedback_for_export() → 过滤条件生效
- `tests/test_feedback_export.py`：
  - 给定 3 条正面反馈 → 导出 CSV 格式正确
  - 短回答（<50 字符）→ 被过滤
  - 重复问题 → 只保留最新
  - 含敏感信息 → 被过滤
- `tests/test_keyword_extractor.py`：
  - 中文文本 → 返回合理关键词
  - 英文文本 → 返回合理关键词
  - 空文本 → 返回空列表

## 不做的事

- 不做前端反馈按钮 UI（主 agent Phase 5 统一做）
- 不做复杂 NLP 关键词提取（不引入 jieba / spaCy）
- 不新增 Alembic 迁移（`qa_feedback` 表已在 Phase 1 迁移中创建）
- 不修改共享文件
- 不在评测集 CSV 中保存 API key 或供应商敏感信息
- 不让真实 API 成为全量测试前提

## 完成标准

- FeedbackService 能正确收集和统计反馈
- 导出脚本能将正面反馈转化为评测集 CSV
- 关键词提取能为评测集生成合理的 expected_answer_keywords
- 反馈 API + 导出 API 正常工作
- 全量 pytest 通过且不退化
