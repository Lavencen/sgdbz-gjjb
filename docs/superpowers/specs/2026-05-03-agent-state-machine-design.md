# Agent 通用状态机架构设计

日期: 2026-05-03

## 1. 背景

当前 Agent 已能完成赐福点赞, 但实现仍是单任务脚本: `BlessingTask` 内部直接串起截图、识别、点击、等待、成功验证和领奖点击。这个结构适合 MVP, 但继续扩展登录处理、弹窗关闭、奖励领取、异常恢复等场景时会变得脆弱。

新的目标是把 Agent 从“点赞脚本”升级为一个小型通用状态机:

```text
截图 -> 状态识别 -> 状态处理 -> 动作后等待/验证 -> 下一轮
```

第一阶段仍只保证现有赐福能力可用, 不引入云控调度和复杂 UI。

## 2. 目标

- 将当前赐福流程拆成独立状态, 而不是一个硬编码任务。
- 支持 YAML 配置简单状态, 例如“识别模板 -> 点击 -> 等待”。
- 支持 Python handler 处理复杂状态, 例如多分支弹窗、登录恢复、滑动查找。
- 统一截图、识别、动作、日志和等待策略。
- 保持现有 `python -m agent.main` 启动方式。
- 保持 ADB/OpenCV/MuMu 本地运行模式可用。

## 3. 非目标

- 不做云控服务端改造。
- 不做 OCR、图像分类模型或强化学习。
- 不做自动登录、账号切换、全游戏挂机。
- 不把 YAML 设计成复杂脚本语言。
- 不一次性重写所有现有模块。

## 4. 核心架构

```text
agent/main.py
  -> Engine.run_forever()
       -> Capture screenshot
       -> RecognizerRegistry.detect()
       -> select best state
       -> execute YAML rule or Python handler
       -> log result
       -> sleep according to result
```

建议新增模块:

```text
agent/engine.py          # 主循环引擎
agent/state.py           # StateMatch, ActionResult, AgentContext 等数据结构
agent/actions.py         # tap, tap_ratio, wait, screenshot 等动作
agent/rules.py           # YAML rule 加载和执行
agent/handlers/          # Python handler 插件目录
agent/recognizers.py     # 模板识别封装, 后续支持区域和组合识别
```

现有模块复用:

```text
agent/adb.py             # ADB 截图与点击
agent/matcher.py         # OpenCV 多尺度模板匹配
agent/logger.py          # JSON 日志与截图保存
agent/config.py          # 配置加载
```

## 5. 状态识别模型

每个状态识别器返回一个 `StateMatch`:

```python
StateMatch(
    name="blessing_like_page",
    confidence=0.96,
    priority=100,
    screenshot=Path(...),
    center=(978, 1529),
    metadata={"template": "templates/like_button.png"},
)
```

选择规则:

1. 只保留 `confidence >= threshold` 的候选状态。
2. 优先级高的状态先处理。
3. 同优先级时选择置信度更高的状态。
4. 没有匹配时进入 `UNKNOWN` 分支, 按全局 `not_found_wait` 等待。

这个规则能解决“成功页上仍残留点赞图标”这类冲突: 只要给领奖页更高优先级, 就会先收奖励。

## 6. YAML 简单状态

YAML 负责表达简单流程: 模板识别、点击、比例点击、等待。

建议新增 `rules.yaml`, 或先放进 `config.yaml` 的 `rules` 段。第一阶段推荐独立 `rules.yaml`, 避免 `config.yaml` 继续膨胀。

示例:

```yaml
rules:
  blessing_reward_page:
    priority: 110
    detect:
      template: "templates/success.png"
      threshold: 0.85
    actions:
      - wait: 1
      - tap_ratio: [0.5, 0.75]
    waits:
      success: 5
      failed: 5

  blessing_like_page:
    priority: 100
    detect:
      template: "templates/like_button.png"
      threshold: 0.85
    actions:
      - tap: [978, 1529]
      - wait: 2
    waits:
      success: 2
      failed: 5
```

第一阶段支持的 action:

```text
tap: [x, y]               # 固定坐标点击
tap_ratio: [rx, ry]       # 按屏幕比例点击, 例如 [0.5, 0.75]
wait: seconds             # 等待
```

## 7. Python Handler

Python handler 用于 YAML 不适合表达的复杂场景。复杂场景包括:

- 一个页面有多个相似按钮, 需要结合区域或上下文判断。
- 点击后可能出现多个不同弹窗, 需要分支处理。
- 需要滑动、重试、回退、关闭弹窗等多步恢复。
- 需要结合时间、次数、冷却或历史状态做决策。

接口草案:

```python
class StateHandler:
    name = "login_page"
    priority = 80

    def detect(self, ctx) -> StateMatch | None:
        ...

    def handle(self, ctx, match: StateMatch) -> ActionResult:
        ...
```

`ctx` 提供:

```text
ctx.adb
ctx.config
ctx.logger
ctx.screenshot
ctx.screen_width
ctx.screen_height
ctx.match_template(...)
ctx.sleep(...)
```

第一阶段可以只实现 handler 注册机制和接口, 不必马上写复杂 handler。

## 8. 赐福流程拆分

当前赐福流程拆成两个状态:

### 8.1 blessing_like_page

识别条件:

```text
templates/like_button.png 匹配成功
```

动作:

```text
点击点赞坐标 (978, 1529)
等待 2s
```

结果:

```text
不在同一状态内强制验证成功页, 交给下一轮状态识别处理。
```

### 8.2 blessing_reward_page

识别条件:

```text
templates/success.png 匹配成功
```

动作:

```text
等待 1s
点击屏幕中下部 tap_ratio [0.5, 0.75]
```

优先级:

```text
blessing_reward_page: 110
blessing_like_page: 100
```

这样即使脚本启动时已经在成功领奖页, 也能直接收奖励。网络或动画延迟时, 下一轮截图也能继续处理, 不依赖固定 2 秒内必须成功。

## 9. 主循环等待策略

建议结果状态:

```text
success      # 状态处理成功
not_found    # 没识别到任何状态
failed       # 识别到状态但动作失败
skipped      # handler 主动跳过
```

等待来源:

1. 当前 rule/handler 明确返回 `next_wait`。
2. 当前 rule 的 `waits.<result>`。
3. 全局 `loop.not_found_wait` 或 `loop.success_cooldown`。

当前配置可继续保留:

```yaml
loop:
  not_found_wait: 15
  success_cooldown: 5
```

## 10. 日志

日志从“任务日志”升级为“状态处理日志”:

```json
{
  "timestamp": "...",
  "state": "blessing_like_page",
  "status": "success",
  "confidence": 0.96,
  "detail": "tap like button",
  "screenshot": "..."
}
```

建议失败和低置信度场景保存截图, 便于后续补模板或调整阈值。

## 11. 错误处理

- ADB 不在线: 启动失败, 写 startup error。
- 截图失败: 记录 capture failed, 等待后重试。
- 模板文件缺失: 启动时校验 rules, 直接报配置错误。
- 动作失败: 记录 failed, 保存截图。
- 多状态同时命中: 使用 priority + confidence 选择。

## 12. 测试策略

单元测试:

- YAML rule 加载与字段校验。
- `tap_ratio` 坐标换算。
- 状态选择 priority/confidence 规则。
- `blessing_reward_page` 优先级高于 `blessing_like_page`。
- 未匹配状态时等待 `not_found_wait`。

回归测试:

- 现有模板匹配测试保留。
- 现有 ADB mock 测试保留。
- 当前赐福功能迁移后仍能执行点赞和领奖动作。

人工验证:

- MuMu 中进入赐福点赞页, 运行 `python -m agent.main`。
- 观察日志出现 `blessing_like_page success`。
- 成功页出现后观察 `blessing_reward_page success`。

## 13. 迁移计划概览

后续实施计划建议分三步:

1. 加基础数据结构和动作层, 不改变现有 `BlessingTask`。
2. 加 YAML rule loader 和 engine, 用测试验证状态选择和动作执行。
3. 把赐福流程迁移成两个 YAML 状态, 删除或兼容保留 `BlessingTask`。

每一步都保持测试可跑, 避免一次性重写导致现场脚本不可用。
