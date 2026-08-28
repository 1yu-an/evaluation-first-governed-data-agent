# 06 A2A-style Spring Boot Starter / A2A 风格 Spring Boot Starter

这是一个**学习型兼容骨架**，用于理解 Spring Boot Starter、Agent Card、skill discovery、task lifecycle。它没有声称实现任何特定版本 A2A 规范的全部细节；真正提交 upstream 前，必须按当时最新官方 spec 补齐 conformance tests（符合性测试）。

## Run / 运行
```bash
mvn test
mvn spring-boot:run
```

Endpoints:
- `GET /.well-known/agent-card.json`
- `POST /a2a/tasks`
- `GET /a2a/tasks/{id}`

## Practice / 实践
1. 对照最新 A2A specification 补 JSON-RPC/HTTP binding。
2. 加 SSE streaming。
3. 加 task cancellation。
4. 加 auth metadata。
5. 做 conformance test suite，再尝试官方仓库 issue/PR。
