from types import SimpleNamespace

import pytest

from app.models import HitterProfile
from app.services import coaching
from app.services.metrics import compute_metrics

from .synthetic import make_pose

FEEDBACK = coaching.CoachingFeedback(
    summary="Solid rotation.",
    strengths=[],
    issues=[],
    next_session_focus="Stay through the ball.",
    caveats=[],
)


class FakeClient:
    def __init__(self, response=None, error=None):
        self.calls = []
        self.response, self.error = response, error
        self.beta = SimpleNamespace(messages=SimpleNamespace(parse=self._parse))

    def _parse(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


@pytest.fixture
def with_key(monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("CLAUDE_MODEL", "claude-opus-5")
    get_settings.cache_clear()


def _install(monkeypatch, client):
    monkeypatch.setattr(coaching.anthropic, "Anthropic", lambda api_key: client)


def test_skipped_without_api_key():
    result = coaching.generate_feedback(compute_metrics(make_pose()), HitterProfile())
    assert result["status"] == "skipped"


def test_sends_metrics_and_returns_feedback(with_key, monkeypatch):
    client = FakeClient(
        SimpleNamespace(stop_reason="end_turn", parsed_output=FEEDBACK, model="claude-opus-5")
    )
    _install(monkeypatch, client)
    result = coaching.generate_feedback(
        compute_metrics(make_pose()), HitterProfile(level="college", height_in=72)
    )
    assert result == {"status": "ok", "model": "claude-opus-5", "feedback": FEEDBACK.model_dump()}

    call = client.calls[0]
    assert call["model"] == "claude-opus-5"
    assert call["output_format"] is coaching.CoachingFeedback
    assert call["fallbacks"] == "default"
    content = call["messages"][0]["content"]
    assert '"hip_rotation"' in content and '"college"' in content


def test_refusal_raises(with_key, monkeypatch):
    _install(monkeypatch, FakeClient(SimpleNamespace(stop_reason="refusal", parsed_output=None, model="x")))
    with pytest.raises(coaching.CoachingError, match="declined"):
        coaching.generate_feedback(compute_metrics(make_pose()), HitterProfile())


def test_connection_error_is_friendly(with_key, monkeypatch):
    import httpx

    err = coaching.anthropic.APIConnectionError(request=httpx.Request("POST", "https://x"))
    _install(monkeypatch, FakeClient(error=err))
    with pytest.raises(coaching.CoachingError, match="Couldn't reach"):
        coaching.generate_feedback(compute_metrics(make_pose()), HitterProfile())
