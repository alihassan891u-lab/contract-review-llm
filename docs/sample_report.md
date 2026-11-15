# Contract review: saas_msa_risky.txt

**Overall risk:** CRITICAL (94/100) · **Findings:** 20 · **Provider:** offline · **Playbook:** default-customer-side

## Summary
- **Type:** SaaS Subscription Agreement
- **Parties:** Northwind Cloud Systems Ltd., Brightline Retail Inc.
- **Effective date:** March 1, 2026
- **Term:** thirty-six (36) months
- **Governing law:** Province of Ontario

## Critical risk (1)

### Unlimited or uncapped liability
*Limitation of Liability · Limitation of Liability · `LOL-001` · rules*

The clause leaves at least one party's liability uncapped.

> …Customer's liability for breach of Sections 3 and 7 shall not be limited.

**Suggested redline:** Except for breaches of confidentiality and a party's indemnification obligations, each party's aggregate liability under this Agreement shall not exceed the fees paid or payable in the twelve (12) months preceding the claim.

## High risk (4)

### Broad IP assignment
*Intellectual Property · IP Ownership / Assignment · `IP-001` · rules*

All IP, possibly including pre-existing materials, transfers to the other party.

> …Customer hereby assigns to Provider all right, title and interest in any feedback, suggestions and improvements, including any pre-existing materials Customer provides to configure…

**Suggested redline:** Exclude pre-existing IP and general know-how; grant a licence to pre-existing IP only as needed to use the deliverables.

### One-sided indemnity
*Indemnification · Indemnification · `IND-001` · rules*

Only your side gives an indemnity; the other party gives none in return.

> …Customer shall defend, indemnify and hold harmless Provider and its affiliates from and against any and all claims, losses, damages and expenses…

**Suggested redline:** Add a reciprocal indemnity from the other party for IP infringement, gross negligence and wilful misconduct.

### Liability cap only protects the other party
*Limitation of Liability · Limitation of Liability · `LOL-002` · rules*

The cap is written for one side only; your own liability may remain uncapped.

> …IN NO EVENT SHALL PROVIDER'S AGGREGATE LIABILITY ARISING OUT OF THIS AGREEMENT EXCEED THE FEES PAID BY CUSTOMER IN THE THREE (3) MONTHS PRECEDING THE CLAIM. PROVIDER…

**Suggested redline:** Make the limitation mutual ("each party's aggregate liability...").

### Long non-compete
*Non-Solicitation and Non-Compete · Non-Compete · `NC-001` · rules*

The non-compete lasts more than 12 months, which is restrictive and may be unenforceable in many places.

> 10. Non-Solicitation and Non-Compete. During the Term and for twenty-four (24) months thereafter, Customer shall not, directly or indirectly, engage any business that competes with the Services, and shall not solicit or…

**Suggested redline:** Limit the non-compete to twelve (12) months and to the specific services delivered under this Agreement.

## Medium risk (10)

### Automatic renewal
*Term · Renewal · `REN-001` · rules*

The contract renews automatically unless someone remembers to cancel it in time.

> …Thereafter this Agreement shall automatically renew for successive twelve (12) month renewal terms unless Customer gives written notice of non-renewal at least one…

**Suggested redline:** Require written confirmation for renewal, or send a renewal reminder at least sixty (60) days before expiry.

### Long notice period to stop renewal
*Term · Renewal · `REN-002` · rules*

The window to give notice of non-renewal is longer than 60 days.

> …Thereafter this Agreement shall automatically renew for successive twelve (12) month renewal terms unless Customer gives written notice of non-renewal at least one hundred twenty (120) days prior to the end of the then-current term.

**Suggested redline:** Reduce the non-renewal notice period to thirty (30) days.

### High late-payment interest
*Fees and Payment · Payment Terms · `PAY-002` · rules*

Late-payment interest is above 1.5% per month.

> …Overdue amounts accrue interest at 2.5% per month. Provider may increase the fees at any time upon thirty (30) days' notice to Customer.

**Suggested redline:** Cap late-payment interest at 1% per month or the statutory rate, whichever is lower.

### Unilateral price increases
*Fees and Payment · Payment Terms · `PRC-001` · rules*

The other party may raise prices without a ceiling.

> …Provider may increase the fees at any time upon thirty (30) days' notice to Customer.

**Suggested redline:** Limit increases to once per year and to the lower of 3% or CPI, with sixty (60) days' written notice.

### Confidentiality ends too soon
*Confidentiality · Confidentiality · `CONF-001` · rules*

Confidentiality obligations expire in under two years.

> …These obligations shall survive for a period of one (1) year following termination of this Agreement.

**Suggested redline:** Extend confidentiality to at least three (3) years after termination, and indefinitely for trade secrets.

### All warranties disclaimed
*Warranties · Warranties · `WAR-001` · rules*

Services or products are provided "as is" with no promise they will work.

> …THE SERVICES ARE PROVIDED "AS IS" AND PROVIDER DISCLAIMS ALL WARRANTIES, EXPRESS OR IMPLIED, INCLUDING ANY WARRANTY OF MERCHANTABILITY OR FITNESS…

**Suggested redline:** Add a warranty that services will be performed in a professional manner and materially conform to the documentation for ninety (90) days.

### Liability cap set very low
*Limitation of Liability · Limitation of Liability · `LOL-003` · rules*

The cap looks small relative to the value at risk.

> …IN NO EVENT SHALL PROVIDER'S AGGREGATE LIABILITY ARISING OUT OF THIS AGREEMENT EXCEED THE FEES PAID BY CUSTOMER IN THE THREE (3) MONTHS PRECEDING THE CLAIM. PROVIDER SHALL NOT BE LIABLE FOR ANY INDIRECT, INCIDENTAL OR CONSEQUENTIAL DAMAGES, INCLUDING…

**Suggested redline:** Raise the cap to at least the fees paid or payable in the preceding twelve (12) months.

### Other party can terminate for convenience
*Termination · Termination for Convenience · `TFC-001` · rules*

Only the other party can walk away without cause.

> …Provider may terminate this Agreement for convenience at any time upon thirty (30) days' written notice. Either Party may terminate this Agreement upon written notice…

**Suggested redline:** Make termination for convenience mutual, with at least ninety (90) days' notice and a pro-rata refund of prepaid fees.

### Non-compete present
*Non-Solicitation and Non-Compete · Non-Compete · `NC-002` · rules*

Any non-compete restricts future business; confirm its scope, territory and duration.

> 10. Non-Solicitation and Non-Compete. During the Term and for twenty-four (24) months thereafter, Customer shall not, directly or indirectly, engage any business that competes with the Services, and shall not solicit or…

**Suggested redline:** Narrow the restriction to named direct competitors and the agreed territory.

### No security incident notification deadline
*Data Protection · Data Protection · `DP-001` · rules*

The clause does not say how quickly a data breach must be reported.

> …Data Protection. Provider will implement reasonable security measures to protect Customer Data and will process personal data…

**Suggested redline:** Require notice of any security incident affecting your data without undue delay and in any case within seventy-two (72) hours.

## Low risk (5)

### Short payment window
*Fees and Payment · Payment Terms · `PAY-001` · rules*

Invoices are due in under 30 days, which may not fit your payables cycle.

> …Provider will invoice Customer monthly in advance and invoices are due within fifteen (15) days of the invoice date. Overdue amounts accrue interest at 2.5% per month. Provider may increase…

**Suggested redline:** Change payment terms to net thirty (30) days from receipt of a valid invoice.

### Other party can assign freely
*Assignment · Assignment · `ASG-001` · rules*

The other party can transfer the contract (for example to a competitor) without your consent.

> …Provider may assign this Agreement without Customer's consent. Customer may not assign this Agreement without Provider's prior written…

**Suggested redline:** Require prior written consent for assignment, except to a successor in a merger with notice.

### Exclusive jurisdiction far from you
*Governing Law and Disputes · Dispute Resolution · `DSP-001` · rules*

All disputes must be brought in one forum chosen by the drafter; check whether it is practical for you.

> …The courts of Toronto, Ontario shall have exclusive jurisdiction over any dispute arising out of this Agreement.

**Suggested redline:** Use the defendant's home courts, or neutral arbitration (e.g. ICC or SIAC) with online hearings.

### Governing law not on preferred list
*Governing Law and Disputes · Governing Law · `GL-001` · rules*

Governed by the laws of Province of Ontario; preferred: England and Wales, New York, Delaware, Singapore.

> laws of the Province of Ontario

**Suggested redline:** Propose the laws of England and Wales.

### Missing clause: Force Majeure
*Whole contract · Force Majeure · `MISSING-force_majeure` · rules*

Clarifies what happens when events outside either party's control occur.

---
_Automated first-pass review. Not legal advice: have a qualified lawyer confirm every finding before relying on it._
