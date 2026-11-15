"""Prompt templates. Kept in one place so they can be versioned and evaluated."""

PROMPT_VERSION = "2026-11-14.1"

SYSTEM = (
    "You are a meticulous commercial contracts lawyer assisting with first-pass contract review. "
    "You only use the contract text you are given. You never invent clauses, numbers or parties. "
    "When asked for JSON you reply with a single valid JSON object and nothing else."
)

CLASSIFY = """Classify each contract clause into one or more clause types from this taxonomy:
{taxonomy}

Rules:
- Use the key names exactly as written above.
- A clause may have up to 3 types (e.g. a liability clause with an uncapped carve-out is both
  "limitation_of_liability" and "uncapped_liability").
- Use "other" only when nothing else fits.
- "hint" is a keyword-based guess; ignore it when the text says otherwise.
- confidence is 0.0-1.0.

Clauses:
{clauses}

Reply with JSON: {{"labels": [{{"clause_id": "c001", "clause_type": "payment", "confidence": 0.9, "rationale": "<10 words>"}}]}}"""

REVIEW = """Review these clauses from a "{contract_type}" agreement for the party described by this playbook:
"{playbook_name}".

Positions the reviewer wants (from the playbook):
{positions}

Issues ALREADY flagged by the rule engine (do not repeat them):
{already}

Clauses:
{clauses}

Find additional material risks only: one-sided obligations, ambiguous wording that could be
used against the reviewer, unusual terms, or conflicts between clauses. Skip boilerplate.
For each issue give:
- clause_id
- title (max 8 words)
- risk: one of low | medium | high | critical
- evidence: an EXACT verbatim quote (max 30 words) copied from that clause
- explanation (1-2 sentences, plain English)
- suggested_redline: replacement or additional wording the reviewer could propose

Reply with JSON: {{"findings": [...]}}. Return {{"findings": []}} if there is nothing material."""

SUMMARY = """Read the start of this contract and extract key facts.

{text}

Reply with JSON:
{{"contract_type": "e.g. Mutual NDA / Master Services Agreement / SaaS Subscription",
  "parties": ["Party legal names as written"],
  "effective_date": "as written, or null",
  "term": "short description, or null",
  "governing_law": "jurisdiction, or null",
  "key_obligations": ["max 5 short bullets"]}}"""

ANSWER = """Answer the question using ONLY the contract excerpts below. Each excerpt starts with its clause id.

{context}

Question: {question}

If the excerpts do not contain the answer, say so and set "grounded" to false.
Cite every clause id you relied on.

Reply with JSON: {{"answer": "...", "citations": ["c004"], "grounded": true}}"""
