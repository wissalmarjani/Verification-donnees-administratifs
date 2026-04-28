from typing import Dict, List

from openai import OpenAI

from app.core.config import settings


def _fallback_answer(question: str, analysis: Dict[str, object], docs: List[Dict[str, object]]) -> str:
    q = question.lower()
    if "inconsisten" in q or "error" in q:
        count = sum(1 for i in analysis["issues"] if i["level"] == "ERROR")
        return f"There are {count} inconsistency errors."
    if "destination" in q:
        destinations = {d.get("destination", "") for d in docs if d.get("destination")}
        return f"Destinations found: {', '.join(sorted(destinations)) or 'not found'}."
    return f"Final status is {analysis['status']} with {len(analysis['issues'])} issue(s)."


def answer_question(question: str, analysis: Dict[str, object], docs: List[Dict[str, object]]) -> str:
    if not settings.openai_api_key:
        return _fallback_answer(question, analysis, docs)

    client = OpenAI(api_key=settings.openai_api_key)
    prompt = (
        "You are an assistant for logistics document consistency checks.\n"
        f"Analysis: {analysis}\nDocuments: {docs}\n"
        f"Question: {question}\n"
        "Answer with concise operational language."
    )
    response = client.responses.create(model="gpt-4.1-mini", input=prompt)
    return response.output_text.strip()
