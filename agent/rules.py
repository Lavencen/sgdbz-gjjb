from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
            detail=f"{self.name} 动作已执行",
            screenshot=match.screenshot,
            next_wait=self.waits.get("success"),
            state=self.name,
            confidence=match.confidence,
        )


def load_rules(path: str | Path = "rules.yaml") -> list[YAMLRule]:
    rules_path = Path(path)
    with open(rules_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if data is None:
        data = {}

    if not isinstance(data, dict):
        raise ValueError("rules.yaml root mapping is required")

    raw_rules = data.get("rules")
    if not isinstance(raw_rules, dict):
        raise ValueError("rules.yaml must contain a 'rules' mapping")

    loaded = []
    for name, raw in raw_rules.items():
        if not isinstance(raw, dict):
            raise ValueError(f"rule '{name}' must be a mapping")

        detect = _optional_mapping(raw.get("detect"), f"rule '{name}' detect")
        template = _resolve_template(rules_path.parent, detect.get("template", ""))
        if not template.exists():
            raise FileNotFoundError(f"Template not found for rule {name}: {template.as_posix()}")

        actions = raw.get("actions") or []
        if not isinstance(actions, list):
            raise ValueError(f"rule '{name}' actions must be a list")

        waits = _optional_mapping(raw.get("waits"), f"rule '{name}' waits")

        loaded.append(
            YAMLRule(
                name=name,
                priority=int(raw.get("priority", 0)),
                template=template,
                threshold=float(detect.get("threshold", 0.85)),
                actions=list(actions),
                waits={key: float(value) for key, value in waits.items()},
            )
        )

    return sorted(loaded, key=lambda rule: rule.priority, reverse=True)


def _resolve_template(base_dir: Path, value: str) -> Path:
    template = Path(value)
    if template.is_absolute():
        return template
    return base_dir / template


def _optional_mapping(value: Any, label: str) -> dict:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a mapping")
    return value
