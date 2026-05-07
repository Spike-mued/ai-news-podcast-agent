import hashlib
import re
from difflib import SequenceMatcher


def compute_content_hash(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def title_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def clean_html(raw: str) -> str:
    clean = re.compile(r"<.*?>")
    text = re.sub(clean, "", raw)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_keywords(text: str, top_n: int = 5) -> list[str]:
    words = re.findall(r"[一-鿿]+|[a-zA-Z]{2,}", text)
    word_freq: dict[str, int] = {}
    for w in words:
        w_lower = w.lower()
        if len(w_lower) < 2:
            continue
        word_freq[w_lower] = word_freq.get(w_lower, 0) + 1
    return sorted(word_freq, key=word_freq.get, reverse=True)[:top_n]


def detect_language(text: str) -> str:
    chinese_chars = len(re.findall(r"[一-鿿]", text))
    if chinese_chars > len(text) * 0.3:
        return "zh"
    return "en"


def truncate_text(text: str, max_length: int = 500) -> str:
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."
