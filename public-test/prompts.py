"""Prompts, verbatim as sent. PREREGISTRATION.md embeds these strings."""
from check_card import norm
HEAD = ("You forecast Kickstarter campaigns. Every project below launched between 14 July 2026 and 9 August 2026 "
        "and ran about 30 days or more. For each project give the probability, between 0 and 1, that it reached its "
        "funding goal. Use only the text below and what you already know. Do not use any tool. "
        "Return one number for every project id, and nothing else.\n")
CARDS_HEAD = "\nEvidence cards for the parent category \"{parent}\". Each card quotes a page published before 14 July 2026:\n"
CARD_LINE = "- {number} | \"{quote}\" ({url}, archived {capture})\n"
PROJ_HEAD = "\nProjects (id | name | blurb{extra}):\n"
def proj_line(r, arm):
    s = "%d | %s | %s" % (r['id'], r['name'], r['blurb'])
    if arm == 4: s += " | category: %s | goal: %s USD | country: %s" % (r['cat'], round(r['usd_goal']), r['country'])
    return s + "\n"
def build(arm, rows, cards=None):
    """arm 2: name+blurb. arm 3: plus the parent's passing cards (>=3, else none). arm 4: arm 3 plus category, USD goal, country."""
    t = HEAD
    if arm in (3, 4) and cards and len(cards) >= 3:
        t += CARDS_HEAD.format(parent=rows[0]['parent']) + "".join(CARD_LINE.format(**dict({k: c.get(k, '') for k in ('number', 'url', 'capture')}, quote=norm(c.get('quote') or ''))) for c in cards)
    t += PROJ_HEAD.format(extra=" | category | goal | country" if arm == 4 else "") + "".join(proj_line(r, arm) for r in rows)
    return t
ODDS_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["odds"], "properties": {"odds": {"type": "array", "items": {
    "type": "object", "additionalProperties": False, "required": ["id", "p"],
    "properties": {"id": {"type": "integer"}, "p": {"type": "number", "minimum": 0, "maximum": 1}}}}}}
CARD_PROMPT = ("Search the web for published statistics about how often Kickstarter projects in the parent category \"{parent}\" reach their funding goal. "
               "Use only pages dated before 14 July 2026. Give up to 5 cards. Each card has: url (the page), quote (copied exactly from that page), "
               "number (the figure in the quote), sample (how many projects the figure covers), population (which projects, which period), year (publication year). "
               "Do not invent a quote. If you find fewer than 5, give fewer.")
CARD_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["cards"], "properties": {"cards": {"type": "array", "maxItems": 5, "items": {
    "type": "object", "additionalProperties": False, "required": ["url", "quote", "number", "sample", "population", "year"],
    "properties": {k: {"type": "string"} for k in ("url", "quote", "number", "sample", "population", "year")}}}}}
