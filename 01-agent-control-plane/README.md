# 01 Agent Control Plane / Agent 控制平面

主项目。实现一个简化的 enterprise agent gateway（企业 Agent 网关）：Tool Registry、Policy Engine、Tool Router、Approval、Audit Log。

## Architecture / 架构

```text
Client -> Spring Boot API -> ToolRouter -> PolicyEngine -> ToolExecutor
                                  |             |
                                  v             v
                              Registry       AuditLog
```

默认 H2 内存数据库；`mysql` profile 可切换 MySQL。

## Run / 运行
```bash
mvn spring-boot:run
```

Demo:
```bash
curl -X POST localhost:8080/api/tools/register -H 'Content-Type: application/json' \
  -d '{"name":"customer.read","description":"Read customer profile","risk":"LOW"}'

curl -X POST localhost:8080/api/execute -H 'Content-Type: application/json' \
  -d '{"actor":"analyst","intent":"read customer 42","requestedTool":"customer.read"}'
```

## Core practice / 核心实践
- Add semantic tool retrieval / 加语义工具检索
- Add JWT + RBAC / 加 JWT 与角色权限
- Add approval workflow / 加审批工作流
- Add OpenTelemetry / 加可观测性
- Benchmark all-tools vs lazy-tool-discovery / 对比全量工具与动态工具发现
