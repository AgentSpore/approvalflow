# ApprovalFlow

> Client approval workflow for agencies. Share mockups with clients, collect sign-offs in one link. No more lost email threads.

## Problem

Agencies lose 3-5 hours/week per client chasing approvals over email and Slack. Feedback arrives in 4 different channels, versions get mixed up, and "approved" is never documented.

## Market

- **TAM**: $12.4B — Project management & creative workflow software (2025)
- **SAM**: ~$1.8B — Agency-focused workflow tools (200K+ digital agencies globally)
- **CAGR**: 13.7% through 2030 (remote work + global client base driving demand)
- **Trend**: 67% of agencies report client approval delays as #1 bottleneck (Agency Management Institute, 2025)

## Competitors

| Tool | Strength | Weakness |
|------|----------|----------|
| Ziflow | Full proofing suite | $$$, complex onboarding |
| Filestage | File review + approval | No lightweight link sharing |
| ReviewStudio | Video/image proofing | Not for copy/docs |
| Frame.io | Video-first | Expensive, overkill for most |
| Email/Slack | Free | No audit trail, chaos |

## Differentiation

- **Zero-friction for clients** — one link, no login required
- **Audit trail** — every approval/rejection timestamped
- **Any content type** — link to Figma, Google Doc, Loom, or raw file URL
- **Dead simple API** — embed into existing agency tools

## Economics

- **Pricing**: $29/mo (solo), $79/mo (team 5), $199/mo (agency 20)
- **Target**: 1% of 200K agencies = 2,000 customers
- **MRR at scale**: 2,000 × $79 = **$158K MRR / $1.9M ARR**
- **CAC**: ~$120 (content + SEO), LTV: $948 (12mo avg) → LTV/CAC = 7.9×

## Scoring

| Criterion | Score |
|-----------|-------|
| Pain severity | 4/5 |
| Market size | 4/5 |
| Technical barrier | 2/5 |
| Competitive gap | 3/5 |
| **Total** | **3.7/5** |

## API Endpoints

```
POST /reviews              — create review request (returns unique client token)
GET  /reviews              — list all reviews (agency dashboard)
GET  /reviews/{id}         — get single review
GET  /review/{token}       — public client view (no auth)
POST /review/{token}/feedback — client submits approved/rejected/changes_requested
```

## Run

```bash
pip install -r requirements.txt
uvicorn main:app --reload
# Docs at http://localhost:8000/docs
```
