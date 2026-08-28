# Interview Questions / 项目面试自测

## Agent Control Plane
- Why a gateway instead of direct tool access? / 为什么不让 Agent 直连工具？
- What is the trust boundary? / 信任边界在哪里？
- How do you prevent prompt injection from triggering destructive tools? / 如何防止提示注入触发危险工具？
- Why must policy be deterministic? / 为什么策略层要尽量确定性？

## Browser Agent
- How do you distinguish “clicked” from “completed”? / 如何区分点了按钮与任务完成？
- What can be verified in DOM vs backend state? / DOM 与后端状态分别适合验证什么？

## Data Agent
- Why is schema alone insufficient? / 为什么只有 schema 不够？
- How do business metric definitions change correctness? / 业务指标定义为什么影响正确性？
- Why use a read-only database credential? / 为什么要用只读数据库账号？

## Coding/Migration Agent
- What is the rollback boundary? / 回滚边界是什么？
- When is compile success insufficient? / 为什么编译通过仍可能不够？

## Research Agent
- How do you handle source disagreement? / 如何处理来源冲突？
- Does newer evidence always win? / 更新的证据是否总是优先？
