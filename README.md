# 风扇消费品知识图谱：Microsoft GraphRAG + Neo4j

这个工程把你的研究方案落成一个可扩展框架：Microsoft GraphRAG 负责从年报、公告、研报、新闻等非结构化文本中抽取实体关系和社区摘要；Neo4j 负责沉淀结构化事实、GraphRAG 输出、产业链关系和量化信号。

上游仓库已经放在同级目录的 `external/` 下：

- `external/microsoft-graphrag`：Microsoft GraphRAG 官方仓库
- `external/neo4j-graphrag-python`：Neo4j 官方 Python GraphRAG 工具
- `external/ms-graphrag-neo4j`：Neo4j 社区的 Microsoft GraphRAG 风格实现

本项目不直接改上游源码，而是在外层做业务适配。这样可以继续跟进 GraphRAG 官方升级，同时把风扇行业本体、内部数据接入、Neo4j 图谱和量化信号稳定保存在本工程。

## 环境

Microsoft GraphRAG 当前要求 Python 3.10-3.12。你本机当前默认 Python 是 3.14，所以建议安装 Python 3.12 后执行：

```powershell
cd fan-ms-graphrag-neo4j
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e ".[dev,docs]"
Copy-Item .env.example .env
```

启动 Neo4j：

```powershell
docker compose up -d neo4j
```

浏览器打开 `http://localhost:7474`，账号 `neo4j`，密码 `fan-kg-password`。

## 一条线跑通 MVP

```powershell
# 1. 检查环境
fan-kg doctor

# 2. 初始化 Neo4j schema 和风扇本体
fan-kg init-schema

# 3. 导入示例结构化数据
fan-kg load-structured --structured-dir data/sample

# 4. 把原始文档整理成 GraphRAG input
fan-kg prepare-docs --source data/raw/documents --target data/graphrag/input

# 5. 初始化 Microsoft GraphRAG 工作区
graphrag init --root data/graphrag --force --model gpt-4.1-mini --embedding-model text-embedding-3-small

# 6. 运行 GraphRAG 索引
graphrag index --root data/graphrag

# 7. 把 GraphRAG 输出 parquet 导入 Neo4j
fan-kg import-graphrag --output-dir data/graphrag/output

# 8. 生成风扇主题量化信号
fan-kg build-signals --structured-dir data/sample --out data/processed/fan_signals.csv
```

## 数据接口

你后续把公司内部数据导出成 CSV 后，放到 `data/raw/structured/`：

- `sw_industry.csv`：申万/数库/其他行业映射
- `company_product_channel.csv`：公司、品牌、产品、渠道、业务暴露度
- `financial_metrics.csv`：财务指标
- `sales_metrics.csv`：销量、销售额、ASP、同比
- `weather_metrics.csv`：区域天气和人口权重
- `commodity_prices.csv`：铜、塑料、钢、物流等成本项
- `material_exposure.csv`：产品对原材料的成本权重
- `market_features.csv`：L1/L2 聚合行情特征

具体字段见 `data/sample/`。

## Neo4j 图谱分层

结构化确定事实：

```text
(:ProductCategory {name:"风扇"})
(:Company)-[:HAS_EXPOSURE_TO]->(:ProductCategory)
(:Company)-[:HAS_METRIC]->(:Metric)
(:ProductCategory)-[:HAS_SALES_METRIC]->(:SalesMetric)
(:Region)-[:HAS_WEATHER]->(:WeatherEvent)
(:Material)-[:HAS_PRICE]->(:CommodityPrice)
(:Security)-[:HAS_MARKET_FEATURE]->(:MarketFeature)
```

GraphRAG 输出：

```text
(:GraphEntity)-[:GRAPHRAG_RELATED_TO]->(:GraphEntity)
(:GraphEntity)-[:MENTIONED_IN]->(:EvidenceChunk)
(:Document)-[:HAS_CHUNK]->(:EvidenceChunk)
(:GraphCommunity)-[:HAS_REPORT]->(:CommunityReport)
(:GraphCommunity)-[:CONTAINS_ENTITY]->(:GraphEntity)
```

量化研究输出：

```text
(:Company)-[:GENERATES_SIGNAL]->(:QuantSignal)
```

## 是否应该“直接修改 Microsoft GraphRAG”？

可以，但不建议把业务代码直接写进上游源码。更稳的方式是：

1. 官方 GraphRAG 保持原样，负责 `init/index/query`。
2. 本项目提供 `fan_kg.graphrag.importer`，读取官方输出 parquet。
3. 本项目提供 `fan_kg.loaders`，接入申万、数库、财务、销量、天气、行情等内部结构化数据。
4. 本项目提供 `fan_kg.signals`，把图谱路径转成可回测信号。

如果后续确实需要改 GraphRAG 的抽取 prompt 或 workflow，优先通过 `data/graphrag/prompts/` 和 `settings.yaml` 修改；只有官方配置无法实现时，再在 `external/microsoft-graphrag` 上开分支改源码。
