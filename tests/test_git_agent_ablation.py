from codecompass.evaluation.git_agent_ablation import _parse_events


def test_parse_events_collects_answer_tools_and_usage() -> None:
    raw = "\n".join(
        (
            '{"type":"tool_use","sessionID":"s1","part":{"tool":"grep","state":{"status":"completed","input":{"pattern":"slug"}}}}',
            '{"type":"text","sessionID":"s1","part":{"text":"answer"}}',
            '{"type":"step_finish","sessionID":"s1","part":{"reason":"stop","tokens":{"total":5,"input":3,"output":2,"reasoning":0,"cache":{"read":1,"write":0}}}}',
        )
    )
    parsed = _parse_events(raw)
    assert parsed["answer"] == "answer"
    assert parsed["tool_calls"] == [{"tool": "grep", "input": {"pattern": "slug"}, "status": "completed"}]
    assert parsed["tokens"] == {"total": 5, "input": 3, "output": 2, "reasoning": 0, "cache_read": 1, "cache_write": 0}
