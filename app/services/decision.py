from dataclasses import dataclass
import re
from typing import Any

import httpx

from app.models.lead import Lead, ResponsePriority


WINDOWS = {
    ResponsePriority.IMMEDIATE: 15,
    ResponsePriority.PRIORITY: 60,
    ResponsePriority.STANDARD: 480,
    ResponsePriority.LOW: 2880,
    ResponsePriority.REVIEW: 240,
}
_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d().\s-]{5,}\d)(?!\w)")


@dataclass(frozen=True)
class DecisionResult:
    summary: str
    priority: ResponsePriority
    window_minutes: int
    confidence: float | None
    model: str | None
    warning: str | None = None


class LeadDecisionEngine:
    def __init__(
        self,
        *,
        ollama_url: str,
        ollama_model: str,
        ollama_timeout_seconds: float,
        typesafe_api_key: str | None,
        typesafe_api_url: str,
        jev_model: str,
        jev_timeout_seconds: float,
        confidence_threshold: float,
        client: httpx.Client | None = None,
    ) -> None:
        self.ollama_url = ollama_url.rstrip("/")
        self.ollama_model = ollama_model
        self.ollama_timeout_seconds = ollama_timeout_seconds
        self.typesafe_api_key = typesafe_api_key
        self.typesafe_api_url = typesafe_api_url
        self.jev_model = jev_model
        self.jev_timeout_seconds = jev_timeout_seconds
        self.confidence_threshold = confidence_threshold
        self.client = client or httpx.Client()

    def decide(self, lead: Lead) -> DecisionResult:
        summary, summary_warning = self._summarize(lead)
        if not self.typesafe_api_key:
            warning = self._combine(summary_warning, "Jev API key is not configured")
            return self._review(summary, warning)

        try:
            response = self.client.post(
                self.typesafe_api_url,
                headers={"Authorization": f"Bearer {self.typesafe_api_key}"},
                json=self._jev_request(lead, summary),
                timeout=self.jev_timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            answer = payload["answers"]["response_speed"]
            priority = ResponsePriority(answer["choice"])
            confidence = float(answer["confidence"])
            review_answer = payload["answers"].get("requires_human_review", {})
            review_value = review_answer.get("noul")
            requires_review = isinstance(review_value, (int, float)) and review_value >= 0.5
            if confidence < self.confidence_threshold or requires_review:
                priority = ResponsePriority.REVIEW
            return DecisionResult(
                summary=summary,
                priority=priority,
                window_minutes=WINDOWS[priority],
                confidence=confidence,
                model=payload.get("model", self.jev_model),
                warning=summary_warning,
            )
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            warning = self._combine(summary_warning, f"Jev decision failed: {type(exc).__name__}")
            return self._review(summary, warning)

    def _summarize(self, lead: Lead) -> tuple[str, str | None]:
        facts = {
            "company": lead.company,
            "source": lead.source,
            "notes": lead.notes,
        }
        fallback = self._fallback_summary(facts)
        try:
            response = self.client.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.ollama_model,
                    "stream": False,
                    "think": False,
                    "prompt": (
                        "Summarize this inbound lead in one factual sentence under 35 words. "
                        "Do not infer facts, urgency, or intent. Return only the sentence.\n"
                        f"Lead facts: {facts}"
                    ),
                    "options": {"temperature": 0, "num_predict": 80},
                },
                timeout=self.ollama_timeout_seconds,
            )
            response.raise_for_status()
            summary = self._clean_summary(str(response.json()["response"]))
            if not summary:
                raise ValueError("empty summary")
            return summary[:1000], None
        except (httpx.HTTPError, KeyError, TypeError, ValueError):
            return fallback, "Local summary model was unavailable; used a factual fallback"

    def _jev_request(self, lead: Lead, summary: str) -> dict[str, Any]:
        return {
            "model": self.jev_model,
            "state": {
                "summary": self._redact_for_jev(summary),
                "company": lead.company,
                "source": lead.source,
            },
            "questions": {
                "response_speed": {
                    "type": "choice",
                    "instructions": "Choose how quickly a human should respond to this inbound lead.",
                    "criteria": {
                        "immediate": "Explicit deadline, active loss, outage, or credible need within hours.",
                        "priority": "Clear buying intent or an important request deserving response within one hour.",
                        "standard": "Ordinary qualified inquiry suitable for response within one business day.",
                        "low": "Exploratory or low-information inquiry suitable for response within two days.",
                        "review": "Suspicious, contradictory, spam-like, or unsafe content needing human review.",
                    },
                },
                "requires_human_review": {
                    "type": "noul",
                    "instructions": "Is the evidence too weak, suspicious, or contradictory for automatic routing?",
                },
            },
        }

    @staticmethod
    def _fallback_summary(facts: dict[str, str | None]) -> str:
        parts = [f"Source: {facts['source']}."]
        if facts["company"]:
            parts.append(f"Company: {facts['company']}.")
        if facts["notes"]:
            parts.append(f"Notes: {facts['notes']}")
        else:
            parts.append("No notes were supplied.")
        return " ".join(parts)[:1000]

    @staticmethod
    def _clean_summary(value: str) -> str:
        summary = value.strip()
        if "</think>" in summary:
            summary = summary.split("</think>", 1)[1].strip()
        if summary.startswith("<think>"):
            return ""
        return summary

    @staticmethod
    def _redact_for_jev(value: str) -> str:
        value = _EMAIL_RE.sub("[email removed]", value)
        return _PHONE_RE.sub("[phone removed]", value)

    def _review(self, summary: str, warning: str) -> DecisionResult:
        priority = ResponsePriority.REVIEW
        return DecisionResult(summary, priority, WINDOWS[priority], None, None, warning)

    @staticmethod
    def _combine(first: str | None, second: str) -> str:
        return "; ".join(part for part in (first, second) if part)
