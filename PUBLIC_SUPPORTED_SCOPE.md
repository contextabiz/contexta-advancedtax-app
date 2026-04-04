# Public Supported Scope

This document is the public-facing scope summary for the current app.

## Positioning

This app is an `advanced Canadian T1 personal tax estimator and review tool`.

It is designed for:

- guided CRA-style slip entry
- personal tax estimation
- worksheet-style review
- refund / balance-owing estimation
- preparer workpaper support

It is best described as a `pure T1 personal tax tool`.

## What The App Supports

### Core Personal T1 Flow

The app currently supports the main personal-return flow, including:

- employment income
- pension / RRSP / RRIF / other income
- interest and dividend income
- rental income
- taxable capital gains
- total income
- net income
- taxable income
- federal tax
- provincial tax
- CPP / EI
- total payable
- payments, credits, refund, and balance owing

### CRA-Style Slip Wizards

The app includes guided wizard input for:

- `T4`
- `T4A`
- `T5`
- `T3`
- `T4PS`
- `T2202`

These wizards are built to let users copy common box amounts directly from slips and forms.

### Major T1 Schedules And Worksheets

The app currently includes dedicated workflows for:

- `Schedule 3` capital gains
- `T776` rental properties
- `Schedule 9` donations and gifts
- `Schedule 11` tuition
- `T2209 / T2036` foreign tax credits

### Common Deductions And Credits

The app currently supports common personal-return items such as:

- RRSP deduction
- FHSA deduction
- RPP contributions
- union / professional dues
- child care expenses
- moving expenses
- support payments deduction
- carrying charges / interest
- other employment expenses
- age amount
- spouse amount
- eligible dependant
- disability amount
- medical expenses
- student loan interest
- tuition claim and transfer-in
- donations
- dividend tax credits

### Household Claim Logic

The app includes a household review engine with support for:

- spouse vs eligible dependant interaction
- caregiver gating
- disability transfer source / availability / usage
- dependant medical gating
- dependant category rules
- multiple dependant support `lite`

This means the app can do more than just collect inputs. It can also explain when a household claim was allowed, blocked, capped, or redirected.

### Provincial Depth

Current provincial depth is strongest in:

- Ontario
- British Columbia
- Alberta

The app also includes province-aware support for:

- Manitoba
- New Brunswick
- Newfoundland and Labrador
- Nova Scotia
- Prince Edward Island
- Saskatchewan

Ontario currently has the deepest worksheet support, with B.C. and Alberta also modelled in stronger detail than the remaining provinces.

### Refundable Credits

The app currently supports a meaningful set of common refundable-credit workflows, including:

- Canada Workers Benefit
- Canada Workers Benefit disability supplement estimator path
- Canada Training Credit
- Medical Expense Supplement
- CPP / EI overpayment refund estimate
- province-specific refundable and benefit-style credits already modelled in the app

### Review And Explainability Features

The app now includes:

- line-by-line return summary
- return package summary
- slip reconciliation
- assumptions / overrides summary
- filing-readiness checklist
- printable client summary
- household review and allocation trace
- federal and provincial breakdowns
- diagnostics before and after calculation

## Best-Fit Return Types

The app is currently strongest for:

- T4-only returns
- T4 + RRSP / FHSA / tuition / donations / medical
- T4 + T5 / T3 investment income
- T4 + rental income
- T4 + capital gains
- moderate family / dependant situations
- workpaper-style return review before filing

For a simpler client-facing explanation of best-fit scenarios and when manual review is still recommended, see `PUBLIC_BEST_FIT_AND_REVIEW_SCENARIOS.md`.

## Short Public Description

If you need a short description for a website, brochure, or client introduction, this is a safe version:

`Advanced Canadian T1 personal tax estimator with CRA-style slip entry, major personal tax schedules, household-claim logic, provincial worksheet support, refundable-credit support, and line-by-line return summaries.`

## Longer Public Description

If you need a slightly more detailed version:

`A pure-T1 Canadian personal tax estimator and review tool built for guided slip entry, major CRA schedule workflows, household claim logic, refund-or-balance estimation, provincial worksheet support, and preparer-style workpaper review.`
