from agent.state import AgentContext


def execute_actions(actions: list[dict], ctx: AgentContext):
    for action in actions:
        execute_action(action, ctx)


def execute_action(action: dict, ctx: AgentContext):
    if "tap" in action:
        x, y = action["tap"]
        ctx.adb.tap(int(x), int(y))
        return

    if "tap_ratio" in action:
        rx, ry = action["tap_ratio"]
        x = round(ctx.screen_width * float(rx))
        y = round(ctx.screen_height * float(ry))
        ctx.adb.tap(x, y)
        return

    if "wait" in action:
        ctx.sleep(float(action["wait"]))
        return

    raise ValueError(f"Unsupported action: {action}")
