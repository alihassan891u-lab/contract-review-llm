"""Clause taxonomy, aligned with the CUAD dataset's category names where possible.

``patterns`` power the offline classifier and act as a cheap pre-filter hint
for the LLM classifier. Weights let strong phrases ("limitation of
liability") outrank incidental words ("liable").
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ClauseType:
    key: str
    label: str
    cuad_name: str | None
    description: str
    patterns: tuple[tuple[str, float], ...]


TAXONOMY: tuple[ClauseType, ...] = (
    ClauseType("parties", "Parties", "Parties", "Who is signing the agreement.",
               ((r"\bby and between\b", 3), (r"\bentered into\b", 1.5), (r"\b(hereinafter|collectively)\b.*\bpart(y|ies)\b", 2))),
    ClauseType("definitions", "Definitions", None, "Defined terms used throughout.",
               ((r"\bdefinitions?\b", 3), (r"\bshall mean\b", 2), (r"\bmeans\b", 0.5))),
    ClauseType("term", "Term / Duration", "Expiration Date", "How long the agreement lasts.",
               ((r"\bterm of (this|the) agreement\b", 3), (r"\binitial term\b", 3), (r"^\W*term\b", 2), (r"\bshall (commence|continue)\b", 1.5))),
    ClauseType("renewal", "Renewal", "Renewal Term", "Automatic or optional renewal.",
               ((r"\bauto(matic(ally)?)?[- ]?renew", 4), (r"\brenewal term\b", 3), (r"\brenew(s|ed|al)?\b", 1.5))),
    ClauseType("termination_for_convenience", "Termination for Convenience", "Termination For Convenience",
               "Right to end the contract without cause.",
               ((r"\bfor (its )?convenience\b", 4), (r"\bwithout cause\b", 3), (r"\bfor any (or no )?reason\b", 2.5))),
    ClauseType("termination_for_cause", "Termination for Cause", None, "Termination on breach or insolvency.",
               ((r"\bmaterial breach\b", 2.5), (r"\bterminat\w*\b", 1.5), (r"\binsolven\w*|\bbankrupt\w*", 1.5))),
    ClauseType("payment", "Payment Terms", None, "Fees, invoicing, late payment.",
               ((r"\binvoice\w*\b", 2), (r"\bfees?\b", 1.5), (r"\bnet\s?\d{2}\b", 3), (r"\bpayment\b", 2), (r"\blate (payment|charge)", 2))),
    ClauseType("price_restrictions", "Price Changes", "Price Restrictions", "Rights to raise prices.",
               ((r"\b(increase|adjust)\w* (the )?(fees|prices?|rates?)\b", 3), (r"\bprice (increase|adjustment)\b", 3))),
    ClauseType("confidentiality", "Confidentiality", None, "Protection of confidential information.",
               ((r"\bconfidential\w*\b", 3), (r"\bnon-?disclosure\b", 3), (r"\bproprietary information\b", 2))),
    ClauseType("ip_ownership", "IP Ownership / Assignment", "Ip Ownership Assignment", "Who owns work product and IP.",
               ((r"\bintellectual property\b", 3), (r"\bwork(s)? (made )?for hire\b", 4), (r"\bhereby assigns?\b", 3), (r"\bownership\b", 1.5))),
    ClauseType("license_grant", "License Grant", "License Grant", "Licences granted between parties.",
               ((r"\bgrants? (to \w+ )?an? (non-?exclusive|exclusive|limited|perpetual|worldwide)", 4), (r"\blicen[cs]e\b", 1.5))),
    ClauseType("indemnification", "Indemnification", None, "Who covers third-party claims and losses.",
               ((r"\bindemnif\w*\b", 4), (r"\bhold harmless\b", 3), (r"\bdefend\b", 1))),
    ClauseType("limitation_of_liability", "Limitation of Liability", "Cap On Liability",
               "Caps and exclusions on damages.",
               ((r"\blimitation of liability\b", 4), (r"\bin no event\b", 2.5), (r"\b(consequential|indirect|incidental|punitive) damages\b", 2.5),
                (r"\baggregate liability\b", 3), (r"\bliabilit(y|ies)\b", 1))),
    ClauseType("uncapped_liability", "Uncapped Liability", "Uncapped Liability", "Carve-outs where liability is unlimited.",
               ((r"\bunlimited liability\b", 4), (r"\bshall not (be )?(limit|cap)\w*\b", 2), (r"\bwithout limit(ation)?\b", 1.5))),
    ClauseType("warranty", "Warranties", "Warranty Duration", "Representations and warranties, disclaimers.",
               ((r"\bwarrant\w*\b", 3), (r"\brepresents? and warrants?\b", 3), (r"\bas is\b", 2), (r"\bmerchantability\b", 3))),
    ClauseType("non_compete", "Non-Compete", "Non-Compete", "Restrictions on competing.",
               ((r"\bnon-?compet\w*\b", 4), (r"\bshall not (directly or indirectly )?(engage|compete)\b", 3), (r"\bcompetitive business\b", 2))),
    ClauseType("non_solicit", "Non-Solicitation", "No-Solicit Of Employees", "No poaching of staff or customers.",
               ((r"\bnon-?solicit\w*\b", 4), (r"\bsolicit\w*\b.*\b(employ\w*|customers?|personnel)\b", 3))),
    ClauseType("exclusivity", "Exclusivity", "Exclusivity", "Exclusive dealing obligations.",
               ((r"\bexclusiv(e|ity)\b", 2.5), (r"\bsole (and exclusive )?(provider|supplier|distributor)\b", 3))),
    ClauseType("assignment", "Assignment", "Anti-Assignment", "Transfer of the contract to others.",
               ((r"\bassign(ment)?\b.*\b(consent|without)\b", 3), (r"^\W*assignment\b", 3), (r"\bchange of control\b", 2.5))),
    ClauseType("governing_law", "Governing Law", "Governing Law", "Which law applies.",
               ((r"\bgoverning law\b", 4), (r"\bgoverned by (and construed in accordance with )?the laws? of\b", 4))),
    ClauseType("dispute_resolution", "Dispute Resolution", None, "Courts, arbitration, venue.",
               ((r"\barbitrat\w*\b", 3), (r"\bjurisdiction\b", 2), (r"\bvenue\b", 2), (r"\bdispute\w*\b", 1.5), (r"\bmediat\w*\b", 2))),
    ClauseType("data_protection", "Data Protection", None, "Personal data, privacy, security.",
               ((r"\bpersonal data\b", 3), (r"\bgdpr\b", 4), (r"\bdata protection\b", 3), (r"\bprivacy\b", 1.5), (r"\bsecurity (breach|incident)\b", 2))),
    ClauseType("insurance", "Insurance", "Insurance", "Required insurance coverage.",
               ((r"\binsurance\b", 3), (r"\bpolicy limits?\b", 2), (r"\bcertificate of insurance\b", 3))),
    ClauseType("audit_rights", "Audit Rights", "Audit Rights", "Right to inspect books and records.",
               ((r"\baudit\w*\b", 3), (r"\binspect\w*\b.*\brecords\b", 2.5))),
    ClauseType("force_majeure", "Force Majeure", None, "Excuse for events beyond control.",
               ((r"\bforce majeure\b", 5), (r"\bacts? of god\b", 3), (r"\bbeyond (its|their) reasonable control\b", 2.5))),
    ClauseType("notices", "Notices", None, "How formal notices are delivered.",
               ((r"^\W*notices?\b", 3), (r"\bnotices? (shall|must) be (given )?in writing\b", 3))),
    ClauseType("entire_agreement", "Entire Agreement", None, "Integration / merger clause.",
               ((r"\bentire agreement\b", 4), (r"\bsupersedes? all prior\b", 3))),
    ClauseType("other", "Other / Boilerplate", None, "Anything not matched above.", ()),
)

BY_KEY = {t.key: t for t in TAXONOMY}
KEYS = [t.key for t in TAXONOMY]

_COMPILED = {t.key: [(re.compile(p, re.I | re.M), w) for p, w in t.patterns] for t in TAXONOMY}


def keyword_scores(text: str, heading: str | None = None) -> dict[str, float]:
    """Score every clause type for a piece of text. Heading matches count double."""
    scores: dict[str, float] = {}
    for key, pats in _COMPILED.items():
        s = 0.0
        for rx, w in pats:
            if rx.search(text):
                s += w
            if heading and rx.search(heading):
                s += 2 * w
        if s:
            scores[key] = s
    return scores


def describe_for_prompt() -> str:
    return "\n".join(f"- {t.key}: {t.description}" for t in TAXONOMY)
