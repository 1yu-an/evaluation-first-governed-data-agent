# 00 Agent Eval Harness / Agent 评测框架

目标：建立最小但可扩展的 regression evaluation（回归评测）系统。不要依赖任何 LLM；先学会把 Agent 行为表示成可判定的结果。

## Run / 运行

```bash
python3 -m src.runner cases/demo_cases.json
```

The legacy command still prints per-case scores and returns `0` only when every
case succeeds. If any case fails, it returns `2`.

## Tests / 测试

```bash
pytest
```

## Markdown report / Markdown 报告

Generate a report with:

```bash
python3 -m src.runner cases/demo_cases.json --report reports/demo.md
```

When `--report` is omitted, no report file is created. When it is provided, the
runner creates parent directories as needed and writes the report as UTF-8.

The report contains:
- Title / 标题
- Total cases / 总案例数
- Passed / 通过数
- Failed / 失败数
- Average score / 平均分
- A case table with `case_id`, `score`, `success`, and `reason`
- A separate Failed cases / 失败案例 section

## Design / 设计

每个 case 包含：
- `input`: 用户任务
- `expected`: 期望最终状态
- `actual`: 模拟 Agent 最终状态
- `metrics`: 可选成本/延迟

评分器检查：task success、policy compliance、verification consistency。

## Practice / 实践任务
1. 加入 partial credit（部分得分）。
2. 增加 tool sequence evaluator（工具序列评测）。
3. 生成 Markdown benchmark report（基准报告）。
4. 将其接入其他 6 个项目。
