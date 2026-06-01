# 风扇消费品 GraphRAG 抽取提示词改造说明

把 Microsoft GraphRAG 初始化后的 `data/graphrag/prompts/extract_graph.txt` 备份后，可在其中加入下面的领域约束。

```text
你正在为量化金融研究构建“风扇消费品产业链知识图谱”。

优先抽取以下实体类型：
COMPANY, BRAND, PRODUCT, PRODUCT_CATEGORY, INDUSTRY, MATERIAL, COMPONENT,
CHANNEL, REGION, FINANCIAL_METRIC, SALES_METRIC, WEATHER_EVENT, COMMODITY,
MARKET_EVENT, POLICY, NEWS_EVENT。

优先抽取以下关系：
BELONGS_TO_INDUSTRY, HAS_SUB_PRODUCT, PRODUCES, OWNS_BRAND, SUPPLIES,
USES_MATERIAL, SELLS_ON, HAS_EXPOSURE_TO, HAS_METRIC, HAS_SALES_METRIC,
HAS_WEATHER, HAS_PRICE, HAS_MARKET_FEATURE, AFFECTS, DRIVES_DEMAND_OF,
COMPETES_WITH。

如果文本提到风扇、电风扇、空气循环扇、塔扇、落地扇、无叶风扇、手持风扇，
请统一识别为 PRODUCT_CATEGORY 或 PRODUCT，并保留原文证据。

如果文本提到公司业务暴露、收入占比、销量、ASP、毛利率、天气、高温、铜价、
塑料、渠道、品牌份额，请优先建立能支持投研解释和因子构造的关系。

每条关系的描述需要包含：关系含义、证据、时间或期间、来源口径、置信度依据。
```

不要在 prompt 中强行要求模型输出 Neo4j Cypher。GraphRAG 负责抽取结构化表，本项目的 `fan-kg import-graphrag` 负责写入 Neo4j。
