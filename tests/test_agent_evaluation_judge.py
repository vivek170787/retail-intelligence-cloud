"""
Tests for agent_evaluation/judge.py's LLM-as-judge scoring. The OpenAI
client is faked (never a real network call) so these tests are fast,
free, and deterministic; openai_config.is_configured/get_openai_client/
get_openai_model are monkeypatched on the judge module itself, since
judge.py imports them by name into its own namespace.
"""

from agent_evaluation import judge as judge_module


class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, content):
        self._content = content

    def create(self, **kwargs):
        return _FakeResponse(self._content)


class _FakeChat:
    def __init__(self, content):
        self.completions = _FakeCompletions(content)


class _FakeClient:
    def __init__(self, content):
        self.chat = _FakeChat(content)


def test_judge_answer_skips_when_not_configured(monkeypatch):
    monkeypatch.setattr(judge_module, "is_configured", lambda: False)
    result = judge_module.judge_answer("q", {}, "some answer")
    assert result["judged"] is False
    assert result["scores"] is None
    assert result["overall"] is None
    assert "OPENAI_API_KEY" in result["error"]


def test_judge_answer_skips_when_no_answer_generated(monkeypatch):
    monkeypatch.setattr(judge_module, "is_configured", lambda: True)
    result = judge_module.judge_answer("q", {}, None)
    assert result["judged"] is False
    assert "No answer" in result["error"]


def test_judge_answer_parses_valid_bare_json(monkeypatch):
    monkeypatch.setattr(judge_module, "is_configured", lambda: True)
    monkeypatch.setattr(judge_module, "get_openai_model", lambda: "test-model")
    content = '{"groundedness": 5, "relevance": 4, "clarity": 3, "rationale": "Solid answer."}'
    monkeypatch.setattr(judge_module, "get_openai_client", lambda: _FakeClient(content))

    result = judge_module.judge_answer("q", {"a": 1}, "answer text")
    assert result["judged"] is True
    assert result["scores"] == {"groundedness": 5, "relevance": 4, "clarity": 3}
    assert result["overall"] == 4.0
    assert result["rationale"] == "Solid answer."
    assert result["error"] is None


def test_judge_answer_extracts_json_from_wrapped_text(monkeypatch):
    monkeypatch.setattr(judge_module, "is_configured", lambda: True)
    monkeypatch.setattr(judge_module, "get_openai_model", lambda: "test-model")
    content = (
        'Here is my assessment:\n```json\n'
        '{"groundedness": 2, "relevance": 2, "clarity": 2, "rationale": "Weak."}\n```'
    )
    monkeypatch.setattr(judge_module, "get_openai_client", lambda: _FakeClient(content))

    result = judge_module.judge_answer("q", {}, "answer")
    assert result["judged"] is True
    assert result["overall"] == 2.0
    assert result["rationale"] == "Weak."


def test_judge_answer_handles_malformed_response(monkeypatch):
    monkeypatch.setattr(judge_module, "is_configured", lambda: True)
    monkeypatch.setattr(judge_module, "get_openai_model", lambda: "test-model")
    monkeypatch.setattr(judge_module, "get_openai_client", lambda: _FakeClient("not json at all"))

    result = judge_module.judge_answer("q", {}, "answer")
    assert result["judged"] is False
    assert result["scores"] is None
    assert result["error"] is not None


def test_judge_answer_handles_out_of_range_score(monkeypatch):
    monkeypatch.setattr(judge_module, "is_configured", lambda: True)
    monkeypatch.setattr(judge_module, "get_openai_model", lambda: "test-model")
    content = '{"groundedness": 9, "relevance": 4, "clarity": 3, "rationale": "Out of range."}'
    monkeypatch.setattr(judge_module, "get_openai_client", lambda: _FakeClient(content))

    result = judge_module.judge_answer("q", {}, "answer")
    assert result["judged"] is False
    assert result["error"] is not None
