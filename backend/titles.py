"""Validate a display-only inbox title; never infer missing enquiry facts."""
import re

from .errors import text


def short_title(value):
    value = text(value, "shortTitle", limit=2000)
    value = " ".join(value.split())
    if re.search(r"[\u3400-\u9fff]", value):
        return value[:15]
    return " ".join(value.split()[:6])[:60]
