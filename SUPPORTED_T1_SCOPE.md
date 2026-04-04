# Supported T1 Scope

This document describes the current supported scope of the app as a `T1 personal tax estimator / workpaper tool`.

## Product Positioning

- The app is a `pure T1 personal tax estimator`.
- The app is `not` a business / self-employment return engine.
- The app is `not` CRA-certified filing software.
- The app is intended for:
  - personal tax estimation
  - worksheet-style review
  - return planning
  - tax-prep workpaper support

## Included

### Core T1 Flow

- `line 10100` employment income
- pension / RRSP / RRIF / other income handling
- `line 12100` interest and investment income
- `line 12600` rental income
- `line 12700` taxable capital gains
- `line 15000` total income
- `line 23600` net income
- `line 25300` net capital loss carryforward used
- `line 26000` taxable income
- federal tax
- provincial tax
- CPP / EI
- total payable
- payments, credits, refund, and balance owing

### Slip Wizards

- `T4`
- `T4A`
- `T5`
- `T3`
- `T4PS`
- `T2202`

### Schedules / Worksheets

- `Schedule 3` capital gains
- `T776` rental properties
- `Schedule 9` donations, carryforward usage, and high-rate handling
  - includes separate treatment of cultural / ecological gifts outside the regular 75% net-income limit
- `Schedule 11` tuition
- `T2209 / T2036` foreign tax credit

### Credits and Deductions

- RRSP / FHSA / RPP / dues / moving / child care / support / carrying charges / other employment expenses
- spouse amount
- eligible dependant
- age amount
- disability amount
- medical expenses
- student loan interest
- tuition claim and transfer-in
- donations
- dividend tax credit
- provincial low-income reduction / tax reduction where modelled

### Household Engine

- spouse / eligible dependant interaction rules
- caregiver gating
- disability transfer source / availability / usage
- dependant medical gating
- dependant category rules
- multiple dependant support `lite`
  - additional dependant caregiver pool
  - additional dependant disability transfer pool
  - additional dependant medical pool

### Provincial Coverage

- Ontario: deepest worksheet support
- British Columbia: strong worksheet support
- Alberta: strong worksheet support
- Manitoba / New Brunswick / Newfoundland and Labrador / Nova Scotia / Prince Edward Island / Saskatchewan:
  - partial to moderate province-aware support
  - selected special schedules / credits

### Refundable Credits

- Canada Workers Benefit `auto + manual override`
  - includes 2025 disability supplement estimator path
- Canada Training Credit `auto + manual override`
- Medical Expense Supplement `auto + manual override`
- CPP / EI overpayment refund estimate from slip withholding totals
- other federal refundable credits input
- other provincial refundable credits input
- province-specific refundable schedules already modelled
  - `ON479` fertility treatment and seniors' public transit credits
  - `BC479` renter's tax credit
  - `BC(S12)` home renovation tax credit
  - `SK479` fertility treatment tax credit
  - `PE428` volunteer firefighter / volunteer search and rescue credit
  - `MB479`
  - `NS479`
  - `NB(S12)` refundable path
  - `NL479`

### Review / Explainability

- line-by-line return summary
- federal breakdown
- provincial breakdown
- household review
- household allocation trace
- post-calculation diagnostics for refundable-credit and payment review
- refundable credits breakdown
- diagnostics and reconciliation warnings

## Not Included

### Business / Self-Employment

- `T2125`
- sole proprietorship income / expense workflow
- self-employed CPP engine
- business-use-of-home
- motor vehicle expense allocation
- inventory
- CCA classes for business assets

### Other Major Gaps

- no full multi-dependant claim-allocation engine
- no complete every-line T1 clone
- no complete every-province worksheet clone
- no CRA e-file / netfile / transmission
- no authorization / consent workflow

## Current Depth Assessment

### Strong Areas

- T slips and guided data entry
- core T1 flow
- Ontario / BC / Alberta provincial worksheet depth
- household restrictions and allocation flow
- foreign tax / tuition / donations / rental / capital gains workflows

### Still Estimator-Level

- some refundable credit eligibility logic
- some provincial special credits
- some household edge cases
- some cross-form diagnostics

## Quick Scope Pitch

If you need to describe the app quickly, the safest short version is:

`Advanced Canadian T1 personal tax estimator for employment, investment, rental, capital gains, tuition, foreign tax, household claims, provincial worksheets, and common refundable credits.`

If you need a slightly more detailed version:

`A pure-T1 Canadian personal tax estimator focused on CRA-style slip entry, major T1 schedules, household-claim logic, Ontario/BC/Alberta worksheet depth, refund-or-balance estimation, and common refundable-credit support.`

## Best-Fit Return Types

The current app is strongest for:

- T4-only returns
- T4 + RRSP / FHSA / tuition / donations / medical
- T4 + T5 / T3 investment income
- T4 + rental income
- T4 + capital gains
- family/dependant returns with moderate complexity

The current app is weaker for:

- self-employment / business returns
- highly complex multi-dependant allocation scenarios
- edge-case provincial planning

## Recommended External Description

Use language like:

`Advanced Canadian T1 personal tax estimator with CRA-style slips, major schedules, household claim logic, federal and provincial worksheets, refundable credit support, and line-by-line return summaries.`

Avoid language like:

- `CRA-certified tax filing software`
- `full business tax software`
- `T2125 self-employment return software`
