"""Sanity checker: ensures the defender's prompt doesn't make the AI a brick."""

from dataclasses import dataclass

from app.config import settings
from app.services.llm import LLMService


@dataclass
class SanityResult:
    """Result of the sanity check."""

    passed: bool
    total_questions: int
    passed_questions: int
    failures: list[str]  # Descriptions of failed checks


def run_sanity_check(llm: LLMService, system_prompt: str) -> SanityResult:
    """Run sanity check questions against the defender's system prompt.

    The AI must still be able to answer basic general knowledge questions.
    If it refuses or gives wrong answers, the prompt is too restrictive.

    Args:
        llm: The LLM service instance.
        system_prompt: The defender's system prompt to test.

    Returns:
        SanityResult with pass/fail details.
    """
    questions = settings.sanity_questions
    expected_keywords = settings.sanity_expected_keywords
    failures: list[str] = []
    passed_count = 0

    for question, keywords in zip(questions, expected_keywords):
        try:
            response = llm.single_turn(system_prompt, question)
            response_lower = response.lower()

            # Check if at least one expected keyword appears in the response
            if any(kw.lower() in response_lower for kw in keywords):
                passed_count += 1
            else:
                failures.append(
                    f"Q: '{question}' → AI said: '{response[:100]}...' "
                    f"(expected one of: {keywords})"
                )
        except Exception as e:
            failures.append(f"Q: '{question}' → Error: {e}")

    # Must pass at least 2 out of 3 questions
    min_pass = max(1, len(questions) - 1)
    passed = passed_count >= min_pass

    return SanityResult(
        passed=passed,
        total_questions=len(questions),
        passed_questions=passed_count,
        failures=failures,
    )
