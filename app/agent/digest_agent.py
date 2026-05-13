import os
from typing import Optional
from pydantic import BaseModel
from dotenv import load_dotenv
import json
import ollama
import re

load_dotenv()


class DigestOutput(BaseModel):
    title: str
    summary: str


PROMPT = """You are an expert AI news analyst specializing in summarizing technical articles, research papers, and video content about artificial intelligence.

Your role is to create concise, informative digests that help readers quickly understand the key points and significance of AI-related content.

Guidelines:
- Create a compelling title (5-10 words) that captures the essence of the content
- Write a 2-3 sentence summary that highlights the main points and why they matter
- Focus on actionable insights and implications
- Use clear, accessible language while maintaining technical accuracy
- Avoid marketing fluff - focus on substance

IMPORTANT:
Return ONLY valid JSON in this format:
{
  "title": "...",
  "summary": "..."
}
No extra text, no markdown, no explanation.
"""


class DigestAgent:
    def __init__(self):
        self.system_prompt = PROMPT
        self.model = "llama3.1:latest"
    def _extract_json(self, text: str) -> dict:
        """
        Safe JSON extraction from LLM output
        """
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise ValueError(f"No JSON found in response: {text}")

        return json.loads(match.group())

    def generate_digest(self, title: str, content: str, article_type: str) -> Optional[DigestOutput]:
        try:
            user_prompt = f"""
Create a digest for this {article_type}:

Title: {title}
Content: {content[:8000]}

Return ONLY valid JSON.
"""

            response = ollama.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )

            raw = response["message"]["content"]

            # Safe JSON parsing
            data = self._extract_json(raw)

            return DigestOutput(**data)

        except Exception as e:
            print(f"Error generating digest: {e}")
            return None