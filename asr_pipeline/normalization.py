"""Conservative Egyptian Arabic and Code-Switching Normalization."""
from __future__ import annotations
import re

ENGLISH_TECH_TERMS = {
    "python", "javascript", "react", "api", "database", "backend", "frontend",
    "docker", "github", "html", "css", "sql", "nosql", "endpoint", "server",
    "client", "json", "rest", "graphql", "git", "deploy", "auth", "jwt"
}

def normalize_egyptian_arabic_transcript(text: str) -> str:
    """
    Conservative text cleaner:
    - Normalizes multiple spaces & carriage returns
    - Cleans excessive repeated punctuation (e.g. '....' -> '.')
    - Preserves Egyptian dialect vocabulary untouched
    - Preserves English technical terms in Latin script
    """
    if not text:
        return ""
    
    t = text.strip()
    t = re.sub(r'[ \t]+', ' ', t)
    t = re.sub(r'\n{3,}', '\n\n', t)
    t = re.sub(r'\.{3,}', '...', t)
    t = re.sub(r'(\?|؟){2,}', '؟', t)
    t = re.sub(r'(!){2,}', '!', t)
    
    # Remove common filler repetition artifacts
    t = re.sub(r'\b(او|اه|أه)( \1){4,}\b', r'\1', t)
    
    return t.strip()
