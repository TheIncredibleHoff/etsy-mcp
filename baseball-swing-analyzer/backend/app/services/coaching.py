"""Turn swing metrics into plain-English coaching feedback with Claude."""

import json
import logging
from typing import Any, Literal

import anthropic
from pydantic import BaseModel, Field

from ..config import get_settings
from ..models import HitterProfile

log = logging.getLogger(__name__)

# Models that support server-side refusal fallbacks ("default" routing).
_FALLBACK_MODELS = {"claude-opus-5", "claude-fable-5-1"}


class Drill(BaseModel):
    name: str
    how_to: str = Field(description="Step-by-step instructions a hitter can follow on their own.")
    why: str = Field(description="How this drill fixes the issue.")


class Strength(BaseModel):
    title: str
    detail: str
    metric_keys: list[str] = Field(description="Keys of the metrics that show this strength.")


class Issue(BaseModel):
    title: str
    priority: Literal["high", "medium", "low"]
    explanation: str = Field(description="What's happening, what it costs the hitter, in plain English.")
    metric_keys: list[str] = Field(description="Keys of the metrics behind this issue.")
    drill: Drill


class CoachingFeedback(BaseModel):
    summary: str = Field(description="Two or three sentences a hitter would read first.")
    strengths: list[Strength]
    issues: list[Issue] = Field(description="Most important first. At most four.")
    next_session_focus: str = Field(description="The one thing to work on next practice.")
    caveats: list[str] = Field(
        description="Measurement limits the hitter should know about for this video, if any."
    )


SYSTEM_PROMPT = """\
You are an experienced baseball hitting coach reviewing a computer-vision \
analysis of one swing. You receive metrics measured from body-pose tracking \
of the video, plus the phases of the swing and any tracking warnings.

Write feedback the hitter (or a parent or coach) can act on:
- Plain English. Explain any term a teenage player might not know.
- Ground every point in the numbers you were given and name the metric keys \
it relies on. Don't invent measurements you weren't given.
- Compare against what's typical for the hitter's level when you know it, \
and say so when a number is only a rough guide.
- Prioritize: the issues that most limit bat speed, consistency, or quality \
of contact come first. Give a concrete drill for each.
- Be encouraging but honest. If the data looks unreliable (low frame rate, \
poor tracking, no clear swing detected), say that plainly rather than \
over-interpreting it.

How the measurements work, so you can judge them:
- Pose tracking follows the body only, not the bat or ball. "Launch angle \
(est.)" is the hands' direction of travel at contact (attack angle), not a \
measured ball launch angle. Bat path is inferred from the hands.
- Rotations are estimated in 3D from a single camera, so absolute degrees \
can be off by 10-20°; timing and relative comparisons are more reliable.
- Timing precision is limited by the frame rate."""


def _user_message(metrics: dict[str, Any], hitter: HitterProfile) -> str:
    payload = {
        "hitter": hitter.model_dump(exclude_none=True),
        "bats": metrics["bats"],
        "video_fps": round(metrics["fps"]),
        "tracking_coverage": metrics["tracking_coverage"],
        "phases": metrics["phases"],
        "metrics": [
            {k: m[k] for k in ("key", "label", "value", "unit", "description")}
            for m in metrics["metrics"]
        ],
        "warnings": metrics["warnings"],
    }
    return (
        "Here is the analysis of the swing. Write coaching feedback.\n\n"
        f"```json\n{json.dumps(payload, indent=2)}\n```"
    )


class CoachingError(RuntimeError):
    pass


def generate_feedback(metrics: dict[str, Any], hitter: HitterProfile) -> dict[str, Any]:
    """Ask Claude for coaching feedback. Returns a JSON-serializable dict."""
    settings = get_settings()
    if not settings.anthropic_api_key:
        return {
            "status": "skipped",
            "error": "ANTHROPIC_API_KEY is not set, so AI coaching feedback was skipped. "
            "Add it to backend/.env and click “Regenerate feedback”.",
        }

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    extra: dict[str, Any] = {}
    if settings.claude_model in _FALLBACK_MODELS:
        # If a safety classifier declines, retry on Anthropic's recommended model.
        extra = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}

    try:
        response = client.beta.messages.parse(
            model=settings.claude_model,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": _user_message(metrics, hitter)}],
            output_format=CoachingFeedback,
            **extra,
        )
    except anthropic.AuthenticationError:
        raise CoachingError("The Anthropic API key was rejected. Check ANTHROPIC_API_KEY.") from None
    except anthropic.RateLimitError:
        raise CoachingError("Claude is rate limiting requests right now. Try again shortly.") from None
    except anthropic.APIStatusError as exc:
        raise CoachingError(f"Claude API error ({exc.status_code}): {exc.message}") from None
    except anthropic.APIConnectionError:
        raise CoachingError("Couldn't reach the Claude API. Check the network connection.") from None

    if response.stop_reason == "refusal":
        raise CoachingError("Claude declined to generate feedback for this analysis.")
    if response.stop_reason == "max_tokens" or response.parsed_output is None:
        raise CoachingError("Claude's response was incomplete. Try regenerating the feedback.")

    return {
        "status": "ok",
        "model": response.model,
        "feedback": response.parsed_output.model_dump(),
    }
