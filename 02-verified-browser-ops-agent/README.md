# 02 Verified Browser Ops Agent / 可验证浏览器操作 Agent

核心原则：**action is not success / 执行动作不等于成功**。Agent 必须读取环境最终状态进行 deterministic verification（确定性验证）。

本基线不强依赖 Playwright，使用 `FakeBrowser` 模拟真实后台页面，便于测试状态机。你完成基线后再替换为 Playwright adapter。

## Run / 运行
```bash
python3 -m src.demo
python3 -m unittest discover -s tests -v
```

## Upgrade / 升级任务
1. 实现 PlaywrightBrowserAdapter。
2. 增加 screenshot + DOM 双通道 perception。
3. 增加 `WAITING_APPROVAL` 状态。
4. 收集成功 trajectory，抽取 reusable skills（可复用技能）。
5. 建立 30+ browser eval tasks。
