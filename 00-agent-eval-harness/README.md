# 00 Agent Eval Harness / Agent 评测框架

目标：建立最小但可扩展的 regression evaluation（回归评测）系统。不要依赖任何 LLM；先学会把 Agent 行为表示成可判定的结果。

## Run / 运行

```bash
python3 -m src.runner cases/demo_cases.json
```

Run the expanded 33-case evaluation set with:

```bash
python3 -m src.runner cases/eval_cases.json
```

The legacy command still prints per-case scores and returns `0` only when every
case succeeds. If any case fails, it returns `2`.

## Tests / 测试

```bash
pytest
```

## Benchmark and Regression Gate / 基准与回归门

Generate deterministic JSON and Markdown benchmark reports:

```bash
python3 -m src.benchmark cases/eval_cases.json \
  --json reports/benchmark.json \
  --markdown reports/benchmark.md
```

Apply the default fixture-conformance gate:

```bash
python3 -m src.benchmark cases/eval_cases.json \
  --json reports/benchmark.json \
  --markdown reports/benchmark.md \
  --gate config/regression_gate.json
```

The benchmark command returns `0` when reports are generated successfully, even
when intentional fixture outcomes fail. It returns `3` only when a configured
Regression Gate threshold is violated. Gate failures print the metric name,
actual value, and threshold.

The generated `reports/` directory is reproducible and ignored by Git.

## Project 03 Integration Benchmark / 03 系统集成基准

Run the real project 03 runtime against the fixed 10-case integration set:

```bash
python3 -m src.integration_benchmark
```

The command creates an isolated temporary SQLite demo database, calls project
03's public `DataAgent.answer` or `evaluate_sql_policy` interface for each case,
adapts the returned fields, evaluates them with project 00, and writes:

- `reports/03-integration.json`
- `reports/03-integration.md`

The integration fixture stores `request`, `expected`, policy expectations, and
`expected_success`; it is rejected if it contains `actual`. Every `actual` is
therefore generated dynamically by project 03 at benchmark time.

The two benchmark types answer different questions:

- Harness Benchmark: the 33-case corpus supplies hand-written adversarial
  `actual` values. Its primary signal is `evaluator_conformance_rate`.
- 03 Integration Benchmark: project 03 supplies real runtime outputs. Its
  `outcome_success_rate` is the current system baseline on the fixed input set.

Do not combine or compare these percentages as if they described the same
population.

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
- A case table with `case_id`, `category`, `score`, `success`, and `reason`
- A dimension table with State, Policy, and Verification applicability, scores,
  pass/fail flags, and reasons for every case
- A separate Failed cases / 失败案例 section

## Dimensional evaluation v0.1 / 维度化评测 v0.1

每个 case 的评测必填字段：
- `id`: 非空案例标识
- `expected`: 对象形式的期望最终状态
- `actual`: 对象形式的模拟 Agent 最终状态

可选字段包括：

- `category`: 报告使用的稳定类别；省略时为 `uncategorized`
- `expected_success`: 对当前手写 `actual` 的预期 evaluator verdict；运行
  benchmark 时为必填 boolean
- `input`: 用户任务
- `metrics`: 成本/延迟
- `tool_policy`: 确定性工具规则
- `required_dimensions`: 当前 case 必须通过的维度；默认三维全部必需

例如，正常查询仍要求完整验证：

```json
"required_dimensions": ["state", "policy", "verification"]
```

正确澄清或正确安全拒绝没有最终查询结果需要验证时，可以声明：

```json
"required_dimensions": ["state", "policy"]
```

该契约属于 case expectation，不属于 runtime `actual`。Evaluator 不根据
`NEED_CLARIFICATION`、`BLOCKED` 等业务状态硬编码适用性规则。字段必须是
由 `state`、`policy`、`verification` 组成的非空、无重复数组。

`actual` 可包含 `tool_calls` 字符串数组，按调用顺序记录观察到的工具轨迹。
`tool_policy` 支持：

```json
{
  "required_tools": ["authenticate", "query_database"],
  "forbidden_tools": ["delete", "shell_exec"],
  "tool_order": [
    ["authenticate", "query_database"],
    ["query_database", "verify"]
  ]
}
```

- `required_tools`: 每个工具至少出现一次
- `forbidden_tools`: 任一工具出现即失败
- `tool_order`: 两端工具都必须出现，且前者第一次出现必须早于后者第一次出现

省略 `tool_policy` 时不应用工具规则，因此旧 demo case 保持兼容。缺失
`tool_calls` 按空轨迹处理；显式提供但格式错误的 trace/rule 会被稳定拒绝。

`input` 和 `metrics` 不参与单 case 评分。Benchmark 会聚合真实提供的
`metrics.latency_ms` 与 `metrics.cost`；当前 33-case corpus 没有这些数据，
因此报告显示 `not available`，不会生成假数字。`expected` 或 `actual`
缺失、或不是 JSON object 时，评测器会明确拒绝该 malformed case。

每个 `EvalResult` 包含三个独立的 `DimensionResult`：

- State：最终状态是否匹配，权重 `0.6`
- Policy：`policy_violation` 与 required/forbidden/order 工具规则，权重 `0.2`
- Verification：`verified` 是否明确为 `true`，权重 `0.2`

每个维度分别提供 `score`、`passed`、`reason` 和 `applicable`。未列入
`required_dimensions` 的维度明确显示为 N/A，而不是 FAIL。`success` 仅要求
case 声明的维度全部通过。

`overall_score` 只在 required dimensions 上按 `0.6 / 0.2 / 0.2` 重新
归一化。例如 Verification N/A 时，State 与 Policy 都通过的得分为
`(1×0.6 + 1×0.2) / 0.8 = 1.0`。旧 case 未声明该字段时仍使用完整三维，
原权重和结果完全不变。

FAIL 与 N/A 不同：FAIL 表示 case 要求该责任且证据不满足；N/A 表示当前
workflow outcome 根本不要求该责任，因此不参与 success、overall score、
失败统计或维度平均。Verification 是 conditional responsibility（条件性
责任），不是每种工作流结果都必须拥有查询结果验证。

总分不能替代维度证据。例如 `overall_score = 0.8` 既可能表示 Policy
失败，也可能表示 Verification 失败。只有逐维度结果才能定位需要修复的
responsibility layer（责任层）。完整契约见 `EVAL_SPEC.md`。

只看 final state 同样不够：Agent 可能完成目标，却在过程中调用禁止的
破坏性 `delete` 工具。此时 State 可以通过，Policy 必须失败，Verification
可以通过，但最终 `success` 必须为 `false`。

现有 CLI 文本保持兼容：仍输出 `score=...`，其中该值是
`overall_score`；任一案例失败时仍返回退出码 `2`。

## Eval vs Benchmark vs Regression Gate

- Eval：判断单个 case 的 State、Policy、Verification 与最终 success。
- Benchmark：聚合固定 Eval Set 的 outcome、conformance、维度、类别和失败指标。
- Regression Gate：将 Benchmark 指标与显式阈值比较，决定是否出现不可接受下降。

For the Harness Benchmark, `outcome_success_rate` 表示手写 `actual` 本身成功的比例，描述被测执行。
`evaluator_conformance_rate` 表示 evaluator verdict 是否匹配
`expected_success`，描述 harness 自身是否符合 fixture 契约。

当前 33-case corpus 是 Harness validation corpus，包含大量故意失败的
对抗案例，并不是真实 Agent production benchmark。因此 outcome success
只有 `8 / 33` 是预期现象，而 evaluator conformance 应为 `33 / 33`。默认
gate 只要求 conformance 为 `1.0`；虽然 CLI 支持可选
`min_outcome_success_rate`，但当前配置没有使用它。

## Stop rule / 停止标准

Project 00 no longer expands as an independent framework after the real project
03 integration. Any new evaluator feature must be justified by a reproducible
bad case emitted by the real project 03 runtime. CI can be considered after the
intended Git history exists; LLM, Docker, MySQL infrastructure, Web UI, generic
benchmark platforms, statistical-significance frameworks, and plugin systems
remain outside this phase.
