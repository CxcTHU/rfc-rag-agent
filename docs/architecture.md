# 架构说明

## 总体流程

```text
资料来源
-> 导入或爬取
-> 文本抽取
-> 清洗
-> 切分 chunk
-> embedding 向量化
-> 向量索引
-> 用户提问
-> 检索召回
-> 组织上下文
-> 大模型回答
-> 返回答案和引用来源
```

## 初始分层

```text
API 层：FastAPI 路由
Schema 层：Pydantic 请求和响应模型
Service 层：导入、切分、检索、问答业务逻辑
DB 层：文档、chunk、问答日志元数据
Model Provider 层：聊天模型和 embedding 模型适配
```

## 第一阶段原则

- 先做工程底座，再做复杂 Agent。
- 先做本地资料导入，再做爬虫。
- 先做检索，再做回答。
- 回答必须能追溯来源。

## 当前实现

阶段 0 已落地最小后端骨架：

```text
app/main.py
  创建 FastAPI 应用，注册路由

app/api/health.py
  提供 GET /health

app/core/config.py
  集中读取应用配置和模型配置占位字段

app/schemas/health.py
  定义健康检查响应结构

tests/test_health.py
  验证 /health 的 HTTP 状态码和 JSON 返回
```

这种结构的目的，是让后续阶段可以自然扩展：

```text
health.py -> documents.py -> search.py -> chat.py
config.py -> database config -> model provider config
health schema -> document/search/chat schemas
```
