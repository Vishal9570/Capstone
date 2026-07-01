import json
import re
from typing import Any, Optional


def strip_code_fences(text: str) -> str:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def extract_json_payload(text: str) -> Any:
    cleaned = strip_code_fences(text)
    first_obj = cleaned.find("{")
    first_arr = cleaned.find("[")

    if first_obj == -1 and first_arr == -1:
        raise ValueError("No JSON object or array found in response")

    if first_obj == -1 or (0 <= first_arr < first_obj):
        start = first_arr
        end = cleaned.rfind("]")
    else:
        start = first_obj
        end = cleaned.rfind("}")

    if start < 0 or end < 0 or end <= start:
        raise ValueError("Malformed JSON response")

    return json.loads(cleaned[start : end + 1])


def get_text_from_response(response: Any) -> str:
    if response is None:
        return ""

    for attr in ("text", "output_text"):
        value = getattr(response, attr, None)
        if isinstance(value, str) and value.strip():
            return value

    message = getattr(response, "message", None)
    if message is not None:
        content = getattr(message, "content", None)
        if isinstance(content, str) and content.strip():
            return content
        if isinstance(content, list):
            parts = []
            for block in content:
                part = getattr(block, "text", None)
                if isinstance(part, str):
                    parts.append(part)
            if parts:
                return "".join(parts)

    content = getattr(response, "content", None)
    if isinstance(content, str) and content.strip():
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            part = getattr(block, "text", None)
            if isinstance(part, str):
                parts.append(part)
        if parts:
            return "".join(parts)

    choices = getattr(response, "choices", None)
    if choices:
        first = choices[0]
        message = getattr(first, "message", None)
        if message is not None:
            text = getattr(message, "content", None)
            if isinstance(text, str):
                return text

    return ""


def compact_text(value: Optional[Any]) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()
