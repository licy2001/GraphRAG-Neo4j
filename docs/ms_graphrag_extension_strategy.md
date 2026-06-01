# Microsoft GraphRAG 改造策略

推荐采用“官方索引器 + 外部适配层”的方式。

## 保持官方 GraphRAG 不变

官方仓库负责：

- 文本切块
- 实体关系抽取
- 社区发现
- 社区摘要
- local/global/drift query

本项目负责：

- 风扇行业本体
- 内部结构化数据接入
- GraphRAG parquet 输出导入 Neo4j
- 图谱检索和量化信号生成

## 何时改 GraphRAG 配置

优先修改：

- `data/graphrag/settings.yaml`
- `data/graphrag/prompts/extract_graph.txt`
- `data/graphrag/prompts/community_report.txt`

适合场景：

- 限定抽取实体类型
- 强化“公司-产品-渠道-财务指标”关系
- 降低无关实体抽取

## 何时改 GraphRAG 源码

只有下列情况才建议在 `external/microsoft-graphrag` 上开分支：

- 需要新增输出表
- 需要改变索引 pipeline 的中间步骤
- 需要接入公司内部模型网关且 LiteLLM 配置不够用
- 需要写自定义 workflow

源码改动要做成小 patch，并记录在本项目 `patches/` 目录，避免未来官方升级时难以合并。
