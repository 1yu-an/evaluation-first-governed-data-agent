# 05 Evidence Deep Research Agent / 证据驱动深度研究 Agent

核心不在“搜索很多网页”，而在 **claim → evidence → source → timestamp → confidence** 的可追溯结构，以及 contradiction detection（冲突检测）。

基线使用本地文档 corpus，方便离线运行。实践时把 `LocalRetriever` 替换为 Web/API retriever。

## Run / 运行
```bash
python3 -m src.demo
python3 -m unittest discover -s tests -v
```

## Upgrade / 升级
- 加网页搜索 connector。
- 同一 claim 至少需要两个独立 source 才能高置信。
- 加 source quality scoring。
- 加 temporal conflict（时间冲突）处理。
- 输出 Evidence Graph JSON + Markdown report。
