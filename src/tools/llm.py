from __future__ import annotations

import json
import os
from typing import Any, Optional

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type


class LlmClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL", "https://api.zhizengzeng.com/v1")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-5.2")
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    @retry(
        reraise=True,
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
    )
    def chat_text(self, system_prompt: str, user_prompt: str) -> str:
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )
        return resp.choices[0].message.content or ""

    @retry(
        reraise=True,
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
    )
    def _extract_json(self, content: str) -> Any:
        text = content.strip()
        if not text:
            raise ValueError("Empty LLM response")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = min([i for i in [text.find("{"), text.find("[")] if i != -1], default=-1)
            end_obj = text.rfind("}")
            end_arr = text.rfind("]")
            end = max(end_obj, end_arr)
            if start == -1 or end == -1 or end <= start:
                raise
            snippet = text[start : end + 1]
            return json.loads(snippet)

    def chat_json(self, schema_hint: str, system_prompt: str, user_prompt: str) -> Any:
        payload = f"{user_prompt}\n\nSchema hint:\n{schema_hint}"
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": payload},
            ],
            temperature=0.2,
        )
        content = resp.choices[0].message.content or ""
        return self._extract_json(content)
