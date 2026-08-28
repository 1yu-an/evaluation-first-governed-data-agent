# Portfolio Roadmap / 求职作品集路线

## First-principles objective / 第一性原理目标

项目的目的不是积累代码，而是产生招聘方可验证的 **engineering evidence（工程能力证据）**。

推荐用以下公式评估投入优先级：

`Project Value = Job Relevance × Technical Depth × Engineering Completeness × Explainability × Differentiation × Finish Probability`

## Your ownership / 你必须亲自掌握

- Problem definition / 问题定义
- System boundaries / 系统边界
- Data model / 数据模型
- API contracts / 接口契约
- Eval specification / 评测标准
- Threat model / 威胁模型
- Failure recovery / 故障恢复
- Benchmark interpretation / 基准结果解释

Agent/Codex 适合承担：CRUD、样板代码、测试实现、重构、脚手架、文档格式化、重复性修复。

## Interview narrative / 面试叙事

不要说：“我用了 LangChain + GPT 做了一个 Agent。”

建议说：

> I designed an evaluation-first agent platform with explicit tool policies, deterministic verification, audit logging and regression tests. / 我设计了一套评测优先的 Agent 平台，包含明确的工具权限、确定性验证、审计日志和回归测试。

然后拿 benchmark、failure case 和 architecture decision 做证据。
