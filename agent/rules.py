from dataclasses import dataclass
from pathlib import Path

import yaml

from agent.actions import execute_actions
from agent.state import ActionResult, AgentContext, ResultStatus, StateMatch


@dataclass
class YAMLRule:
    name: str
    priority: int
    template: Path
    threshold: float
    actions: list[dict]
    waits: dict[str, float]

    def detect(self, ctx: AgentContext) -> StateMatch | None:
        result = ctx.match_template(self.template, self.threshold)
        if not result.matched:
            return None
        return StateMatch(
            name=self.name,
            confidence=result.confidence,
            priority=self.priority,
            screenshot=ctx.screenshot,
            center=result.center,
            metadata={
                "template": self.template.as_posix(),
                "scale": result.scale,
            },
        )

    def handle(self, ctx: AgentContext, match: StateMatch) -> ActionResult:
        execute_actions(self.actions, ctx)
        return ActionResult(
            status=ResultStatus.SUCCESS,
            detail=f"{self.name} actions executed",
            screenshot=match.screenshot,
            next_wait=self.waits.get("success"),
            state=self.name,
            confidence=match.confidence,
        )


def load_rules(path: str | Path = "rules.yaml") -> list[YAMLRule]:
    rules_path = Path(path)
    with open(rules_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    raw_rules = data.get("rules")
    if not isinstance(raw_rules, dict):
        raise ValueError("rules.yaml must contain a 'rules' mapping")

    loaded = []
    for name, raw in raw_rules.items():
        detect = raw.get("detect") or {}
        template = _resolve_template(rules_path.parent, detect.get("template", ""))
        if not template.exists():
            raise FileNotFoundError(f"Template not found for rule {name}: {template.as_posix()}")

        loaded.append(
            YAMLRule(
                name=name,
                priority=int(raw.get("priority", 0)),
                template=template,
                threshold=float(detect.get("threshold", 0.85)),
                actions=list(raw.get("actions") or []),
                waits={key: float(value) for key, value in (raw.get("waits") or {}).items()},
            )
        )

    return sorted(loaded, key=lambda rule: rule.priority, reverse=True)


def _resolve_template(base_dir: Path, value: str) -> Path:
    template = Path(value)
    if template.is_absolute():
        return template
    return base_dir / template
