# Public Limitations And Boundaries

This document is the public-facing limitations summary for the current app.

## Product Boundary

This app is a `personal T1 estimator and review tool`.

It is `not` positioned as:

- CRA-certified filing software
- EFILE / NETFILE transmission software
- business tax software
- self-employment return software

## Not Included

### No T2125 / Business Workflow

The app does not currently include:

- `T2125`
- sole proprietorship income / expense workflow
- self-employed CPP calculation
- business-use-of-home workflow
- vehicle allocation for business use
- inventory workflow
- business CCA class handling

### Not A Full CRA-Certified Filing Product

The app does not currently include:

- CRA-certified filing status
- electronic filing transmission
- authorization / consent workflow
- signature workflow
- CRA reject-code handling
- submission tracking

### Some Areas Are Still Estimator-Level

Although the app is now quite deep for a T1 estimator, some areas still remain estimator-level rather than full CRA box-by-box reproduction.

Examples include:

- some refundable-credit eligibility logic
- some provincial special-credit logic
- some household edge cases
- some cross-form consistency checks
- some province-specific worksheet details

## Current Practical Limitation

The app is strong for estimation, review, and workpaper support.

It should not yet be described publicly as:

- a full every-line CRA return clone
- full every-province worksheet software
- full business-return software
- filing software for all tax scenarios

## Weaker Return Types

The app is currently weaker for:

- self-employment / business returns
- highly complex multi-dependant allocation scenarios
- edge-case provincial planning
- situations requiring every special provincial schedule

## Safe Public Wording

Good wording:

- `advanced Canadian T1 personal tax estimator`
- `personal tax review and worksheet tool`
- `guided T1 slip-entry and return-estimation tool`
- `preparer workpaper support for personal returns`

Avoid wording like:

- `CRA-certified tax filing software`
- `full-service business tax software`
- `T2125 self-employment return software`
- `complete replacement for certified filing platforms`

## Best Use Case

The safest public positioning is:

`Best for advanced T1 personal tax estimation, guided slip entry, schedule review, household-claim review, and refund-or-balance planning.`
