"""Deterministic quality checks for Vision Lab prompt candidates."""
from dataclasses import dataclass
from typing import List, Sequence


@dataclass(frozen=True)
class QualityIssue:
    code: str
    severity: str
    message: str


@dataclass(frozen=True)
class QualityReport:
    passed: bool
    score: int
    issues: Sequence[QualityIssue]
    metrics: dict


def validate_prompt_quality(
    prompt: str,
    *,
    protected_instructions: str = "",
    max_chars: int = 12000,
    min_chars: int = 40,
) -> QualityReport:
    """Check usable length, instruction integrity, and basic prompt hygiene."""
    issues: List[QualityIssue] = []
    text = prompt if isinstance(prompt, str) else ""
    if not text.strip():
        issues.append(QualityIssue("EMPTY_PROMPT", "error", "Prompt is empty."))
    if len(text) < min_chars:
        issues.append(QualityIssue("PROMPT_TOO_SHORT", "warning", "Prompt may be missing useful visual detail."))
    if len(text) > max_chars:
        issues.append(QualityIssue("PROMPT_TOO_LONG", "warning", f"Prompt exceeds the selected model limit of {max_chars} characters."))
    if protected_instructions and protected_instructions not in text:
        issues.append(QualityIssue("INSTRUCTION_LOSS", "error", "An explicit user instruction is missing or altered."))
    if text and len(text.split()) < 8:
        issues.append(QualityIssue("LOW_DETAIL", "warning", "Prompt contains very little descriptive detail."))
    score = 100
    for issue in issues:
        score -= 35 if issue.severity == "error" else 12
    score = max(0, score)
    return QualityReport(
        passed=not any(item.severity == "error" for item in issues),
        score=score,
        issues=tuple(issues),
        metrics={"characters": len(text), "words": len(text.split()), "max_chars": max_chars},
    )


def quality_report_to_dict(report: QualityReport):
    return {
        "passed": report.passed,
        "score": report.score,
        "issues": [
            {"code": item.code, "severity": item.severity, "message": item.message}
            for item in report.issues
        ],
        "metrics": dict(report.metrics),
    }
