"""Prompt templates, builder and a rule-based prompt quality analyser."""
import re
from dataclasses import dataclass, field

TECHNIQUES = {
    "Zero-shot": "Directly state the task with clear instructions and output format — no examples.",
    "Few-shot": "Show 2–5 input → output examples so the model infers the pattern and format.",
    "Chain-of-Thought": "Ask the model to reason step by step before giving the final answer.",
    "Role / Persona": "Assign an expert role to set vocabulary, depth and tone.",
    "Structured Output (JSON)": "Force a machine-readable schema for reliable downstream parsing.",
    "ReAct (Reason + Act)": "Interleave Thought → Action → Observation for tool-using agents.",
    "Self-Consistency": "Generate several reasoning paths and pick the majority answer.",
}

TECHNIQUE_SUFFIX = {
    "Zero-shot": "",
    "Few-shot": "",
    "Chain-of-Thought": "Think through the problem step by step, then give the final answer on a separate line starting with 'Answer:'.",
    "Role / Persona": "",
    "Structured Output (JSON)": "Return ONLY valid JSON matching this schema: {schema}",
    "ReAct (Reason + Act)": "Use this loop until done:\nThought: <reasoning>\nAction: <tool>[<input>]\nObservation: <result>\nFinish with 'Final Answer: <answer>'.",
    "Self-Consistency": "Solve the problem in 3 independent ways, then report the answer that appears most often.",
}


@dataclass
class PromptSpec:
    technique: str = "Zero-shot"
    role: str = ""
    task: str = ""
    context: str = ""
    constraints: list = field(default_factory=list)
    output_format: str = ""
    examples: list = field(default_factory=list)  # list of (input, output)
    schema: str = '{"answer": "string"}'


def build_prompt(s: PromptSpec) -> str:
    parts = []
    if s.role:
        parts.append(f"You are {s.role}.")
    if s.context:
        parts.append(f"### Context\n{s.context.strip()}")
    if s.task:
        parts.append(f"### Task\n{s.task.strip()}")
    if s.constraints:
        parts.append("### Constraints\n" + "\n".join(f"- {c}" for c in s.constraints if c.strip()))
    if s.examples and s.technique == "Few-shot":
        ex = "\n\n".join(f"Input: {i}\nOutput: {o}" for i, o in s.examples)
        parts.append(f"### Examples\n{ex}")
    if s.output_format:
        parts.append(f"### Output format\n{s.output_format.strip()}")
    suffix = TECHNIQUE_SUFFIX.get(s.technique, "").replace("{schema}", s.schema)
    if suffix:
        parts.append(suffix)
    return "\n\n".join(parts)


VAGUE = ["something", "stuff", "things", "etc", "good", "nice", "some", "maybe", "kind of", "a bit"]
ACTION_VERBS = ["write", "summarize", "summarise", "classify", "extract", "explain", "generate", "translate",
                "list", "compare", "analyze", "analyse", "rewrite", "create", "draft", "identify", "evaluate", "convert"]


def estimate_tokens(text: str) -> int:
    """~4 characters per token heuristic (close to GPT/Claude tokenizers for English)."""
    return max(1, round(len(text) / 4))


def analyse(prompt: str) -> dict:
    """Score a prompt on 6 dimensions (0-10) and return improvement tips."""
    p = prompt.lower()
    words = re.findall(r"[a-z']+", p)
    tips, s = [], {}

    s["Role"] = 10 if re.search(r"\byou are\b|\bact as\b|\bas an? (expert|senior|professional)", p) else 2
    if s["Role"] < 5:
        tips.append("Add a role/persona (e.g. 'You are a senior data analyst').")

    verbs = [v for v in ACTION_VERBS if re.search(rf"\b{v}\b", p)]
    s["Clarity"] = min(10, 4 + 3 * len(verbs)) - min(4, sum(p.count(f" {v} ") for v in VAGUE))
    if not verbs:
        tips.append("Start the task with a clear action verb (summarize, classify, extract…).")
    if any(f" {v} " in p for v in VAGUE):
        tips.append("Replace vague words (something, stuff, good…) with specific requirements.")

    s["Context"] = 10 if ("context" in p or len(words) > 60) else (6 if len(words) > 30 else 3)
    if s["Context"] < 6:
        tips.append("Give background: audience, purpose, data source or domain.")

    s["Format"] = 10 if re.search(r"json|table|bullet|markdown|format|csv|list of|\d+ (words|sentences|points)", p) else 2
    if s["Format"] < 5:
        tips.append("Specify the output format and length (e.g. '5 bullet points, under 100 words').")

    s["Constraints"] = 10 if re.search(r"constraint|must|do not|don't|avoid|only|limit|under \d+", p) else 3
    if s["Constraints"] < 5:
        tips.append("Add constraints/guardrails (what to avoid, tone, length limits).")

    s["Examples"] = 10 if re.search(r"example|input:|output:", p) else (6 if "step by step" in p else 3)
    if s["Examples"] < 5:
        tips.append("Add 1–3 examples (few-shot) for consistent style and format.")

    s = {k: max(0, min(10, v)) for k, v in s.items()}
    overall = round(sum(s.values()) / len(s) * 10)
    return {"scores": s, "overall": overall, "tips": tips, "tokens": estimate_tokens(prompt), "words": len(words)}
