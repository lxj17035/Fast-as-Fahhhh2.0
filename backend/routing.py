"""Conservative deterministic association; no provider, HTTP or send authority."""
import re


def association(text, candidates, reply_target=None):
    content = text.strip()
    if re.match(r"^/(start|help)(?:@[\w]+)?(?:\s|$)", content, re.I):
        return "command", None
    distinct = re.search(
        r"\b(new|another|separate|additional|independent|second|third)\b.{0,50}"
        r"\b(quotation|quote|order|request|enquiry)\b", content, re.I)
    if distinct:
        return "new", None
    if reply_target in candidates:
        return "assigned", reply_target
    if not candidates:
        return "new", None
    followup = re.match(
        r"^(actually|instead|change|update|yes\b|no\b|correct|size|colou?r|quantity|"
        r"address|delivery|pickup|confirm|amend|revision|combine|for (?:the|that)|"
        r"\d+\s*(?:pcs|pieces|shirts|units)|更改|数量|颜色|尺寸|确认)", content, re.I)
    if followup and len(candidates) == 1:
        return "assigned", candidates[0]
    return "needs_assignment", None
