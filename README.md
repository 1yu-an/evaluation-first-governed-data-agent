# AI Engineering Internship Project Lab

> English title / 中文说明：面向 AI Application Engineer、LLM Engineer、Applied AI Engineer、FDE 实习/求职的完整项目实践包。

本仓库不是“教程 Demo 合集”，而是一套围绕 **architecture（架构）→ execution（执行）→ verification（验证）→ evaluation（评测）→ observability（可观测性）→ governance（治理）** 构建的作品集实践。

## Reviewer entrypoint / 求职审查入口

如果你正在审查 AI Application Engineer、LLM Application Engineer 或 FDE
候选项目，请优先查看：

1. [03 Governed MySQL Data Agent](03-governed-mysql-data-agent/README.md)：当前完成的
   evaluation-first governed agent 主案例、快速演示、架构、安全边界和工程演进证据。
2. [00 Agent Eval Harness](00-agent-eval-harness/README.md)：03 使用的固定评测集、
   维度化评测、Benchmark Report 和 Regression Gate。

03 README 是该项目面向 reviewer 的权威入口；`CURRENT_STATE.md` 只记录简洁的
仓库状态快照。

## Projects / 项目

| ID | Project | Core proof / 核心能力证明 | Suggested time / 建议投入 |
|---|---|---|---:|
| 00 | Agent Eval Harness | evaluation-first（评测优先） | 8-15h |
| 01 | Agent Control Plane | MCP-style registry, policy, audit, routing（工具注册、策略、审计、路由） | 50-80h |
| 02 | Verified Browser Ops Agent | action + deterministic verification（执行 + 确定性验证） | 35-60h |
| 03 | Governed MySQL Data Agent | semantic layer + SQL safety（语义层 + SQL 安全） | 35-60h |
| 04 | Java Migration Agent | repo automation + compile/test loop（仓库自动化 + 编译测试闭环） | 30-50h |
| 05 | Evidence Deep Research Agent | evidence graph + contradiction detection（证据图 + 冲突检测） | 25-45h |
| 06 | A2A Spring Boot Starter | protocol adapter + starter design（协议适配 + Starter 设计） | 15-30h |

## Recommended order / 推荐顺序

1. `00-agent-eval-harness`：先学会定义“成功”。
2. `03-governed-mysql-data-agent`：利用你已有 MySQL 基础，最快形成可展示结果。
3. `01-agent-control-plane`：作为整个 Portfolio 的主项目。
4. `02-verified-browser-ops-agent`：补真实环境执行与验证。
5. `04-java-migration-agent`：把 Java 背景变成差异化。
6. `06-a2a-spring-boot-starter`：做协议与生态集成能力。
7. `05-evidence-deep-research-agent`：补研究、证据链和信息综合。

## Important rule / 重要原则

**Codex/Agent may implement details; you own correctness. / Agent 可以写细节，但“什么叫正确”必须由你定义。**

每个项目都要求你能解释：
- Why this architecture? / 为什么这样设计？
- What can fail? / 哪里会失败？
- How do you verify reality? / 如何验证真实世界状态？
- How do you benchmark it? / 如何评测？
- What is the security boundary? / 安全边界是什么？
- What trade-offs were made? / 做了哪些取舍？

## Local-first / 本地优先

项目默认尽量提供 mock/local mode（本地模拟模式），无需付费 LLM API 即可学习核心工程逻辑。真实模型接入点通过接口保留，你可以后续让 Codex 接 OpenAI/Anthropic/Gemini/本地模型。

## Shared commands / 通用命令

```bash
python scripts/validate_all.py
```

该脚本检查 Python 语法、JSON/YAML-like 配置、关键目录和 Java 源文件基础结构。Spring Boot 项目如本机有 Maven，可进一步运行：

```bash
cd 01-agent-control-plane && mvn test
cd ../06-a2a-spring-boot-starter && mvn test
```

## Portfolio delivery checklist / 作品集交付标准

每个主项目完成后至少包含：
1. Architecture diagram / 架构图
2. 20+ eval cases / 20 个以上评测用例
3. Failure analysis / 失败分析
4. Benchmark table / 基准数据表
5. Threat model / 威胁模型
6. Demo script / 演示脚本
7. README with decisions / 设计决策说明
8. One concrete improvement over baseline / 至少一个相对 baseline 的可量化改进

详见 `docs/portfolio-roadmap.md` 与每个项目 README。
