# Competitive intelligence — sourcing, grading, bias control

> Method card loaded whenever a claim about the outside world (a market, a competitor, a regulation,
> a funding scheme) enters a deliverable. It governs **how you may know**, not what you conclude.

## 🏷️ Evidence grading — mandatory

Every external figure carries a grade. No grade, no figure.

| Grade | Meaning | Typical source | What it licenses you to say |
|---|---|---|---|
| ✅ **Verified** | Cross-checked against a primary, authoritative source | Official register, legal text, filed accounts, signed contract | "X is…" |
| 📊 **Measured** | Produced by us, reproducibly | Production query, telemetry, tracker export | "We operate…" — with the query preserved |
| 🌐 **Declarative** | Stated by an interested party | Vendor website, press release, pitch deck, analyst summary | "X claims…" — never "X has…" |
| 📐 **Estimated** | Our own order of magnitude | Derivation from public counts | "In the order of…" + the derivation shown |

> The single most damaging habit in competitive work is promoting 🌐 to ✅ between the draft and the
> final version. A vendor's "200 customers" is a marketing statement; it may count sites, licences,
> contracts or pilots, and it is never dated.

## ⚖️ Comparability rules

1. **Never sum across vendors.** Different units (site, customer, seat, municipality, population served).
2. **Always date a figure.** An undated market claim is unusable within a year.
3. **Ask what the denominator is.** "40 % adoption" — of whom, over what period, measured how?
4. **Prefer counts you can verify independently** (public contract awards, registers) over self-reported ones.
5. **Distinguish operated volume from imported volume** in your own numbers too — the same discipline applies inward.

## 🔍 Where to look, in order

```
1. Primary law and official portals        → obligations, deadlines, definitions (the demand drivers)
2. Public procurement data                 → who actually won what, at what price, when
3. Public catalogues and frameworks        → who is referenced, under which category
4. Vendor sites                            → positioning and self-description (🌐 only)
5. Sector press and analyst notes          → consolidation signals, funding rounds, M&A
6. Our own corpus                          → RFP analyses, lost deals, support themes, feature matrices
```

> Step 6 is usually the richest and is usually skipped. An organisation that answers tenders is already
> sitting on a structured description of its market, written by its buyers.

## 🧠 Bias control

| Bias | How it shows up | Counter-move |
|---|---|---|
| **Confirmation** | The study concludes what the sponsor already said | Write the strongest case against the recommendation before writing the recommendation |
| **Availability** | The competitors named are the ones we met last month | Enumerate from catalogues and award data, not from memory |
| **Capability projection** | "We could reuse 70 % of the platform" | Have engineering score the reuse independently |
| **Survivorship** | Only won or active deals inform the picture | Read the lost deals first |
| **Recency** | A single recent tender reframes the whole market | Require a pattern across at least three observations before calling it a trend |
| **Home-field** | Assuming the incumbent is technically behind | Separate product age from commercial strength — they are not correlated |

## 🥷 Ethics and legality

```
✅ Public sources, published procurement data, vendor materials, official registers
✅ Asking customers what they compared us against — openly
✅ Reading a competitor's public documentation and pricing

❌ Misrepresenting who you are to obtain information
❌ Confidential documents obtained from a third party, including via a new hire
❌ Contract or tender material covered by a confidentiality undertaking
❌ Scraping in breach of a platform's terms
```

> The hard rule: if quoting the source in the deliverable would be embarrassing, the source does not go
> in the deliverable — and does not inform it either.

## 📝 Writing rules

- Attribute in the sentence, not in a footnote: "Vendor X states 200 references 🌐".
- Keep a source list with live links; internal sources cited by repository path.
- Mark every estimate with its derivation, inline.
- When two sources disagree, say so and keep both. A resolved contradiction that was never real is worse
  than an open one.
- Separate **observation** from **interpretation** typographically — the reader must be able to accept the
  first and reject the second.

## 🚫 Anti-patterns

```
❌ Unsourced market sizes ("a €2bn market") with no derivation
❌ Competitor tables where every row is from the competitor's own homepage
❌ A trend called from one data point
❌ Quoting a regulation's deadline without checking the consolidated current text
❌ Reusing last year's study's figures without re-dating them
❌ Anonymous claims: "it is known that…"
```
