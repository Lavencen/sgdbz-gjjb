from pathlib import Path
from unittest.mock import MagicMock

import pytest

from agent.rules import YAMLRule, load_rules
from agent.state import AgentContext, ResultStatus


def test_load_rules_sorts_by_priority(tmp_path):
    templates = tmp_path / "templates"
    templates.mkdir()
    (templates / "like.png").write_bytes(b"fake")
    (templates / "success.png").write_bytes(b"fake")
    rules_file = tmp_path / "rules.yaml"
    rules_file.write_text(
        """
rules:
  like:
    priority: 100
    detect:
      template: "templates/like.png"
      threshold: 0.85
    actions:
      - tap: [1, 2]
    waits:
      success: 2
  reward:
    priority: 110
    detect:
      template: "templates/success.png"
      threshold: 0.85
    actions:
      - tap_ratio: [0.5, 0.75]
    waits:
      success: 5
""",
        encoding="utf-8",
    )

    rules = load_rules(rules_file)

    assert [rule.name for rule in rules] == ["reward", "like"]
    assert rules[0].priority == 110
    assert rules[1].actions == [{"tap": [1, 2]}]


def test_load_rules_rejects_missing_template(tmp_path):
    rules_file = tmp_path / "rules.yaml"
    rules_file.write_text(
        """
rules:
  missing:
    priority: 1
    detect:
      template: "templates/missing.png"
      threshold: 0.85
    actions:
      - wait: 1
""",
        encoding="utf-8",
    )

    try:
        load_rules(rules_file)
    except FileNotFoundError as exc:
        assert "templates/missing.png" in str(exc)
    else:
        raise AssertionError("expected FileNotFoundError")


@pytest.mark.parametrize(
    ("yaml_text", "expected_message"),
    [
        ("- rules\n- nope\n", "root mapping"),
        ("[]\n", "root mapping"),
        ("false\n", "root mapping"),
        ("0\n", "root mapping"),
        ("plain scalar\n", "root mapping"),
        (
            """
rules:
  bad: "not a mapping"
""",
            "rule 'bad' must be a mapping",
        ),
        (
            """
rules:
  bad:
    detect: "not a mapping"
    actions:
      - wait: 1
""",
            "rule 'bad' detect must be a mapping",
        ),
        (
            """
rules:
  bad:
    detect:
      template: "templates/like.png"
    actions:
      wait: 1
""",
            "rule 'bad' actions must be a list",
        ),
        (
            """
rules:
  bad:
    detect:
      template: "templates/like.png"
    actions:
      - wait: 1
    waits:
      - success
""",
            "rule 'bad' waits must be a mapping",
        ),
    ],
)
def test_load_rules_rejects_malformed_yaml_shapes(tmp_path, yaml_text, expected_message):
    templates = tmp_path / "templates"
    templates.mkdir()
    (templates / "like.png").write_bytes(b"fake")
    rules_file = tmp_path / "rules.yaml"
    rules_file.write_text(yaml_text, encoding="utf-8")

    with pytest.raises(ValueError, match=expected_message):
        load_rules(rules_file)


def test_yaml_rule_detect_returns_state_match():
    match_result = MagicMock()
    match_result.matched = True
    match_result.confidence = 0.91
    match_result.center = (10, 20)
    match_result.scale = 1.0
    ctx = MagicMock(spec=AgentContext)
    ctx.screenshot = Path("screen.png")
    ctx.match_template.return_value = match_result
    rule = YAMLRule(
        name="like",
        priority=100,
        template=Path("templates/like.png"),
        threshold=0.85,
        actions=[{"tap": [1, 2]}],
        waits={"success": 2},
    )

    state_match = rule.detect(ctx)

    assert state_match is not None
    assert state_match.name == "like"
    assert state_match.confidence == 0.91
    assert state_match.center == (10, 20)
    assert state_match.metadata["template"] == "templates/like.png"


def test_yaml_rule_handle_executes_actions_and_returns_wait(monkeypatch):
    calls = []
    monkeypatch.setattr("agent.rules.execute_actions", lambda actions, ctx: calls.append(actions))
    ctx = MagicMock(spec=AgentContext)
    rule = YAMLRule(
        name="reward",
        priority=110,
        template=Path("templates/success.png"),
        threshold=0.85,
        actions=[{"wait": 1}, {"tap_ratio": [0.5, 0.75]}],
        waits={"success": 5},
    )
    match = MagicMock()
    match.screenshot = Path("screen.png")
    match.confidence = 0.92

    result = rule.handle(ctx, match)

    assert calls == [[{"wait": 1}, {"tap_ratio": [0.5, 0.75]}]]
    assert result.status == ResultStatus.SUCCESS
    assert result.state == "reward"
    assert result.detail == "reward 动作已执行"
    assert result.next_wait == 5
