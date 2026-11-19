# Carbon-Neon 智能混合编排器实战手册 (Playbook & Templates)

本文档提供 `carbon-neon-orchestrator` 的路由速查表、防失真 Brief 模板、`share` 隔离工作区安全合入协议与「两振出局」接管流程。

## 目录
1. [路由决策与接管速查矩阵](#1-路由决策与接管速查矩阵)
2. [零失真 Brief 模板（含图片透传与热派生）](#2-零失真-brief-模板含图片透传与热派生)
3. [首轮启动与看板推进标准序列](#3-首轮启动与看板推进标准序列)
4. [`workspace: "share"` 并发开发与安全合入协议](#4-workspace-share-并发开发与安全合入协议)

---

## 1. 路由决策与接管速查矩阵

| 任务场景 / 运行时状态 | 执行主体与模型 | 关键动作 |
| :--- | :--- | :--- |
| 纯答疑，或 **已知单文件 + 改动 ≤20 行 + 零构建循环 + 改完即止** | **Carbon 亲自秒办** | 走「微调快车道」，不拉起 Swarm，几秒内直接改完回复 |
| 陌生仓库目录扫描、查引用链、日志提炼、`monitor` 哨兵 | `gemini-4-neon-medium` / `low` | `swarm add` 并发只读摸底，保持主会话干净 |
| 常规模块开发、多文件重构、写单测、跑构建验证、分支合入 | `gemini-4-neon-high`（默认主力） | Carbon 锁契约与文件边界，派 Neon 干活（多写开 `share`） |
| 复杂状态机/异步逻辑、棘手 Bug 排查、深度 Verifier | `gemini-4-neon-xhigh` | `swarm add` 直接用 `xhigh` 高思考档位 |
| **高精尖数学/物理/IK 建模、高精细度单文件艺术动画、顶层核心原语** | **Carbon 亲自操刀核心** | Carbon 亲手写核心算法/骨架，外围脚手架与测试再派 Neon |
| **Neon 连续 2 轮修不好同一 Bug / 质量明显拉胯 / 用户不满意** | **Carbon 立即强制接管** | 触发「两振熔断」，停止让 Neon 盲试，Carbon 亲自读源码修复 |
| 多轮深度讨论后上下文极重、写文字 Brief 易漏隐含细节 | `neon-high` / `xhigh` + `fork` | `swarm{action:"add", ..., fork:"coordinator"}` 继承完整记忆 |
| `neon-high` 遇配额预警/耗尽 | 同系余量档位或 Carbon 兜底 | 先查 `swarm{action:"models"}`，用 `action:"model"` 无损续跑 |

---

## 2. 零失真 Brief 模板（含图片透传与热派生）

### 模板 A：侦察节点 (Neon Recon Worker)
- **配置**：`model: "gemini-4-neon-medium"`，`workspace: "inherit"`

```text
负责只读侦察模块：<模块/目录路径>。切勿修改任何文件。
请快速查明：
1. 核心入口文件、关键类/函数签名及数据流向；
2. 与 <目标特性/问题> 相关的精确文件路径与行号；
3. 该模块现有的测试文件与运行命令。
完成后以 `@coordinator [done]` 开头精炼汇报上述三项事实。
```

### 模板 B：并行实现节点（含图片/附件防失真透传）
- **配置**：`model: "gemini-4-neon-high"`（高难逻辑用 `"gemini-4-neon-xhigh"`），多写并发必设 `workspace: "share"`（若前置讨论极深可加 `fork: "coordinator"`）

```text
负责实现子任务：<一句话目标>。

【必读原始素材与参考文件（严禁跳过）】
- 开工第一步请先调用 `read_file` 直接查看以下用户原图/参考文件：
  1. `<用户上传图片或参考文件的绝对路径，如 /path/to/.user_uploaded/xxx.png>`
  2. `<参考源码绝对路径>`

【文件边界（One Writer Per File）】
- 你唯一允许新增/修改的文件：<精确文件路径列表>
- 严禁修改其他任何文件。

【Carbon 锁定的接口契约与视觉/逻辑要点】
<粘贴精确的接口签名、数据结构，或 Carbon 提炼的关键架构约束>

【验收与提交要求】
1. 完成编码并补充对应测试；
2. 运行验证命令：`<如 pnpm test xxx && pnpm typecheck>`，确保零报错；
3. （若在 share 工作区）提交变更：`git add <你的文件> && git commit -m "<提交信息>"`，获取 `git rev-parse HEAD` 的 Commit SHA；
4. 完成后发帖：`@coordinator [done] <改动摘要> | commit: <SHA> | 验证结果: <测试输出摘要>`。若遇契约冲突或阻塞，立即发帖 `@coordinator [blocked] <原因>`。
```

### 模板 C：独立验证节点 (Neon Verifier Worker)
- **配置**：`model: "gemini-4-neon-high"` 或 `"gemini-4-neon-xhigh"`，`workspace: "inherit"`

```text
你是本轮改动的独立验证官（Verifier）。请只读审查并运行测试，切勿直接修改业务代码。
请对照看板 #<序号> 的汇报执行检查：
1. 运行完整验证命令：`<测试/构建/类型检查命令>`；
2. 对照接口契约走查边界条件（空值、异步竞态、错误处理、样式与深浅色主题兼容）；
3. 全部通过请发帖：`@coordinator [done] 验证通过：<测试与审查摘要>`；
4. 若有缺陷，列出精确文件名、行号与修复建议，点名对应作者（或 `@coordinator`）。
```

---

## 3. 首轮启动与看板推进标准序列

```json
// 1. 命名集群
{"action": "title", "title": "核心模块重构与测试验证"}

// 2. 启动并行 Neon 节点（多写并发开启 share；需要继承深上下文时加 "fork": "coordinator"）
{"action": "add", "name": "auth-api", "model": "gemini-4-neon-high", "workspace": "share", "brief": "..."}
{"action": "add", "name": "state-sync", "model": "gemini-4-neon-xhigh", "workspace": "share", "brief": "..."}

// 3. 若当前会话 <skills> 中存在 swarm_monitor，挂载低开销哨兵
{"action": "add", "name": "monitor", "model": "gemini-4-neon-low", "brief": "You are this swarm's stall monitor. Load the swarm_monitor skill and follow it. Post only to break a stall."}
```
- 首轮回复末尾**单独一行原样输出**返回结果中的 `open_board` 值，随后立即结束本轮工具调用等待唤醒。
- 推进过程中若某个节点第 1 次失败，给精准指导或 `swarm{action:"model", name:"...", model:"gemini-4-neon-xhigh"}` 升档；若**第 2 次仍失败**，立即停止派活，由 Carbon 亲自接管修复！

---

## 4. `workspace: "share"` 并发开发与安全合入协议

1. Carbon 从各 Worker 的 `[done]` 报告收集 `commit: <SHA>`，指派 `integrator`（`model: "gemini-4-neon-high"`, `workspace: "inherit"`）执行合入。
2. `integrator` 在主工作区按序执行 `git cherry-pick --no-commit <SHA1> <SHA2>`（或保留提交历史直接 `git cherry-pick`），跑通测试确认工作树正常后向 `@coordinator [done]` 汇报。
3. **Carbon 亲自抽查关键文件的最终代码/Diff**，确认无误后，才调用 `swarm{action: "kill", name: "<worker>"}` 清理临时 `share` 节点（切记先合入再 `kill`）。
