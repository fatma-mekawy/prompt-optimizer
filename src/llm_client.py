"""
LLM Client - Ollama local integration with:
- Chain-of-Thought prompting
- Retry logic with exponential backoff
- Response caching
- Structured JSON output
- Runs Gemma3:1b locally without using `ollama serve`
"""

import json
import re
import time
import hashlib
import logging
import requests
from typing import List

from src.models import LLMAnalysisResult, Message

logger = logging.getLogger(__name__)

import requests

# GROQ_API_KEY = "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"

# GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
import os
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY environment variable is not set")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

def call_llm(prompt: str):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7
    }

    response = requests.post(GROQ_URL, headers=headers, json=payload)
    response.raise_for_status()

    return response.json()["choices"][0]["message"]["content"]
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

# Simple in-memory cache: hash(prompt) -> result
_cache: dict = {}
CACHE_MAX_SIZE = 100


def _cache_key(prompt: str, history_summary: str) -> str:
    raw = prompt + "|" + history_summary
    return hashlib.md5(raw.encode()).hexdigest()


def _build_cot_prompt(user_prompt: str, history: List[Message]) -> str:
    """
    Build a Chain-of-Thought prompt that instructs the model to reason
    step-by-step before producing structured output.
    """
    history_text = ""
    if history:
        recent = history[-5:]
        history_text = "\n".join(f"{m.role}: {m.content}" for m in recent)

    return f"""You are an expert prompt engineer. Your job is to analyze a user's prompt and improve it.

{"**Conversation history:**" + chr(10) + history_text + chr(10) if history_text else ""}

**User's prompt:**
{user_prompt}

Think step by step (Chain-of-Thought):
Step 1: What is the user trying to achieve? What is missing?
Step 2: Is the prompt vague, ambiguous, or missing context?
Step 3: What specific improvements would make this prompt better?
Step 4: Write an improved version.

After reasoning, return ONLY a JSON object with this exact structure (no markdown, no extra text):
{{
  "reasoning_steps": ["step1 reasoning", "step2 reasoning", "step3 reasoning", "step4 reasoning"],
  "issues": ["issue1", "issue2"],
  "suggestions": ["suggestion1", "suggestion2"],
  "improved_prompt": "the full improved prompt here"
}}"""


def _clean_json(text: str) -> str:
    """Remove markdown fences and extract JSON."""
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*", "", text)
    match = re.search(r"\{.*\}", text, re.DOTALL)
    return match.group(0) if match else text.strip()


def _parse_response(raw: str, user_prompt: str) -> LLMAnalysisResult:
    """Parse LLM response into structured output with fallback."""
    cleaned = _clean_json(raw)
    try:
        data = json.loads(cleaned)
        return LLMAnalysisResult(
            issues=data.get("issues", []),
            suggestions=data.get("suggestions", []),
            improved_prompt=data.get("improved_prompt", user_prompt),
            reasoning_steps=data.get("reasoning_steps", [])
        )
    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"JSON parse failed: {e}. Using fallback.")
        return LLMAnalysisResult(
            issues=["Could not parse model response"],
            suggestions=["Try rephrasing your prompt with more context"],
            improved_prompt=user_prompt,
            reasoning_steps=["Model response was not valid JSON"]
        )


def analyze_prompt_with_llm(user_prompt: str, history: List[Message]) -> LLMAnalysisResult:
    """
    Main function: sends prompt to Groq API, returns structured result.
    Includes retry logic and caching.
    """

    history_summary = " ".join(m.content[:50] for m in history[-3:])
    key = _cache_key(user_prompt, history_summary)

    # --- Cache check ---
    if key in _cache:
        logger.info("Cache hit")
        return _cache[key]

    full_prompt = _build_cot_prompt(user_prompt, history)

    last_error = None

    for attempt in range(MAX_RETRIES):
        try:
            # ✅ Groq call (returns string مباشرة)
            raw_text = call_llm(full_prompt)

            # Parse LLM output
            result = _parse_response(raw_text, user_prompt)

            # --- Cache handling ---
            if len(_cache) >= CACHE_MAX_SIZE:
                oldest_key = next(iter(_cache))
                del _cache[oldest_key]

            _cache[key] = result

            return result

        except Exception as e:
            last_error = str(e)

            if attempt < MAX_RETRIES - 1:
                wait = RETRY_DELAY * (2 ** attempt)
                logger.warning(
                    f"Attempt {attempt+1} failed: {last_error}. Retrying in {wait}s..."
                )
                time.sleep(wait)

    raise Exception(last_error or "Groq LLM request failed after retries")