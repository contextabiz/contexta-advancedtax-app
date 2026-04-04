# Near-Complete Personal Tax Estimator Backlog

This backlog turns the current roadmap into buildable app work items for the Streamlit UI and `tax_engine` package.

## Phase 1
Goal: move from advanced estimator to a stronger, broadly usable personal tax workpaper tool for common returns.

### P1-01 Full `Schedule 3` engine
Priority: High
Area: `tax_engine`, `app.py`

Scope:
- Replace the current simplified capital gains schedule with a fuller `Schedule 3` workflow.
- Support multiple dispositions with explicit gain/loss calculation.
- Distinguish current-year gains from current-year losses before taxable inclusion.
- Apply net capital loss carryforward usage more explicitly.

Forms / lines:
- `Schedule 3`
- `line 12700`
- `line 25300`

UI:
- Build a `Schedule 3 Wizard`
- Add per-disposition cards:
  - description
  - proceeds
  - adjusted cost base
  - outlays and expenses
  - property type
- Add a `Schedule 3 Summary` table

Acceptance criteria:
- The app shows gross gains, gross losses, net gains/losses, and taxable capital gains.
- Negative dispositions are handled before applying the 50% inclusion rate.
- Carryforward usage is visible in the return summary.

### P1-02 Full `T776` rental engine
Priority: High
Area: `tax_engine`, `app.py`

Scope:
- Replace the current rental net-income shortcut with a fuller rental statement flow.
- Support multiple properties with income and expense categories.
- Keep CCA optional but separate from cash expenses.

Forms / lines:
- `T776`
- `line 12599`
- `line 12600`

UI:
- Build a `T776 Wizard`
- Add per-property cards:
  - address/label
  - gross rents
  - advertising
  - insurance
  - interest and bank charges
  - property taxes
  - utilities
  - repairs and maintenance
  - management and administration
  - travel
  - office expenses
  - other expenses
  - CCA
- Add a rental totals summary

Acceptance criteria:
- The app computes net rental income from category totals.
- Multiple properties aggregate correctly.
- The return summary shows the rental total entering the T1 flow.

### P1-03 Stronger `T2209 / T2036` foreign tax flow
Priority: High
Area: `tax_engine`, `app.py`

Scope:
- Upgrade the current estimator-style foreign tax logic into a more faithful worksheet flow.
- Separate non-business foreign income and tax more clearly.
- Show intermediate lines used in the ceiling calculation.

Forms / lines:
- `T2209`
- `T2036`
- `line 40500`
- provincial foreign tax credit lines

UI:
- Keep the existing worksheet section, but restructure it as line-based cards.
- Add a summary block for:
  - foreign income used
  - foreign tax paid used
  - federal ceiling
  - residual tax for provincial credit
  - provincial ceiling

Acceptance criteria:
- Federal and provincial foreign tax credits each show their own limit path.
- Overrides are optional, not required.
- The result page clearly shows what amount was claimed and what amount was capped.

### P1-04 Complete `Schedule 11` tuition and transfer flow
Priority: High
Area: `tax_engine`, `app.py`

Scope:
- Expand tuition handling beyond direct claim plus carryforward totals.
- Support available amount, current-year claim, and transfer logic more explicitly.

Forms / lines:
- `Schedule 11`
- `line 32300`
- tuition transfer logic

UI:
- Build a `Schedule 11 / Tuition Wizard`
- Add sections for:
  - current-year T2202 tuition
  - prior-year carryforward
  - current-year claim
  - transfer from spouse/partner
  - unused balance carried forward

Acceptance criteria:
- The app separates tuition available from tuition claimed.
- Carryforward and transfer amounts are visible in the calculation summary.
- T2202 wizard data flows cleanly into the tuition worksheet.

### P1-05 Expand core T1 line coverage
Priority: High
Area: `tax_engine`, `app.py`

Scope:
- Fill the biggest common gaps in the main return flow.
- Separate currently bundled income and deduction buckets where needed.

Forms / lines:
- `line 12100`
- `line 12600`
- `line 12800`
- `line 13000`
- `line 21400`
- `line 21900`
- `line 22000`
- `line 22100`
- `line 22900`
- `line 43700`
- `line 47600`
- `line 48200`
- `line 48400`

UI:
- Add missing common line inputs under `2) Income and Investment`, `3) Deductions`, and `5) Payments and Withholdings`
- Add a clearer line-by-line T1 return summary tab

Acceptance criteria:
- Users can map common real-life slips and adjustments into proper T1 lines with less manual approximation.
- Main return summary displays the added lines explicitly.

### P1-06 Diagnostics and reconciliation v1
Priority: High
Area: `app.py`, `tax_engine`

Scope:
- Add warnings for likely missing or conflicting data.
- Start basic slip-to-return reconciliation.

UI:
- Add a `Diagnostics` block near the calculate button or in the results area.
- Flag cases such as:
  - T4 tax withheld entered but no employment income
  - foreign tax paid without foreign income
  - tuition entered twice through wizard and manual claim
  - negative carryforward claim exceeding available amount

Acceptance criteria:
- The app shows non-blocking but visible warnings before or after calculation.
- Users can identify high-risk input mistakes quickly.

## Phase 2
Goal: improve accuracy for family, transfer, carryforward, and refundable-credit-heavy returns.

### P2-01 Full household claim interaction engine
Priority: High
Area: `tax_engine`, `app.py`

Scope:
- Make spouse, eligible dependant, caregiver, and disability-related logic more complete.
- Model mutual exclusivity and restriction rules more explicitly.

Forms / lines:
- `line 30300`
- `line 30400`
- `line 30425`
- `line 30450`
- `line 30500`
- `line 31800`
- `line 32600`
- `line 33400`
- `line 33500`

UI:
- Build a `Household Status Wizard`
- Add cards for:
  - marital status and change date
  - separation
  - support payments
  - children / dependants
  - shared custody
  - infirm dependant / caregiver status
  - disability transfer

Acceptance criteria:
- Auto-claims respect key restriction combinations.
- The result page shows which household claims were allowed, denied, or reduced.

### P2-02 Refundable credits engine
Priority: High
Area: `tax_engine`, `app.py`

Scope:
- Add major refundable credits instead of relying mostly on manual overrides.
- Keep province-specific credits modular.

Forms / lines:
- federal refundable credit lines as supported
- provincial `*479` and equivalent refundable schedules

UI:
- Add a `Refundable Credits` subsection inside `4) Credits, Carryforwards and Special Forms`
- Group by federal and province

Acceptance criteria:
- Refundable amounts are shown separately from non-refundable credits.
- The payments/refund section clearly identifies refundable credits as part of the refund result.

### P2-03 Donation carryforward and high-rate engine
Priority: High
Area: `tax_engine`, `app.py`

Scope:
- Improve `Schedule 9` to better model current-year plus carried-forward donations.
- Apply high-rate donation treatment more transparently.

Forms / lines:
- `Schedule 9`
- `line 34900`

UI:
- Upgrade `Donation Carryforward by Year` into a proper wizard
- Add:
  - available donation by year
  - current-year claim
  - remaining carryforward
  - high-rate eligible amount

Acceptance criteria:
- Users can see how much was claimed from current year vs carryforward.
- High-rate donation handling is visible and auditable.

### P2-04 Tuition carryforward and transfer limits by year
Priority: High
Area: `tax_engine`, `app.py`

Scope:
- Add stronger controls for tuition carryforward usage and transfer limits.
- Prevent double claiming between current year and carryforward.

Forms / lines:
- `Schedule 11`
- related tuition transfer lines

UI:
- Extend the tuition wizard to include year-by-year availability and claim usage.

Acceptance criteria:
- Claimed amounts cannot silently exceed available balances.
- Remaining balances are shown after the current return estimate.

### P2-05 Province-wide worksheet depth expansion
Priority: Medium-High
Area: `tax_engine/provinces`, `app.py`

Scope:
- Push more provinces closer to Ontario/BC depth.
- Expand line-by-line worksheet clones for provincial credits and reductions.

Forms / lines:
- `AB428`
- `BC428`
- `MB428`
- `NB428`
- `NL428`
- `NS428`
- `PE428`
- related `*479` or special schedules

UI:
- Standardize provincial worksheet tabs:
  - claim amount
  - credit amount
  - tax after each stage

Acceptance criteria:
- Each supported province has a clearer, more complete worksheet path.
- Provincial credit logic is no longer heavily dependent on generic manual fields.

### P2-06 Diagnostics and reconciliation v2
Priority: Medium-High
Area: `tax_engine`, `app.py`

Scope:
- Expand warnings into rule-based validation.
- Add cross-form checks.

UI:
- Add a `Review Checks` table with severity levels:
  - info
  - warning
  - high-risk

Acceptance criteria:
- The app identifies more missing-form and duplicate-entry scenarios.
- Diagnostics feel like a tax-prep review pass, not just a calculator warning list.

## Phase 3
Goal: approach a near-complete personal tax workpaper system with strong explainability and maintainability.

### P3-01 Complete slip-to-line mapping
Priority: High
Area: `app.py`, `tax_engine`

Scope:
- Expand all wizard-supported slips so more common boxes map directly into line items.
- Reduce dependence on manual fallback fields.

Forms:
- `T4`
- `T4A`
- `T5`
- `T3`
- `T4PS`
- `T2202`

UI:
- Add per-slip summaries showing:
  - boxes entered
  - return lines affected
  - amount used

Acceptance criteria:
- Users can enter common slips with minimal manual duplication.
- The app clearly shows what each slip contributed to the return.

### P3-02 Line-by-line return package
Priority: High
Area: `app.py`, `tax_engine`

Scope:
- Turn the current result summary into a fuller working-paper package.
- Present T1 and schedules in a review-friendly structure.

UI:
- Add tabs for:
  - `T1 Return`
  - `Federal Credits`
  - `Provincial Worksheet`
  - `Schedules`
  - `Payments and Refund`

Acceptance criteria:
- The user can trace the return from slips and inputs to final tax.
- The result pages feel like a real prep file, not only a calculator output.

### P3-03 Calculation trace and audit trail
Priority: High
Area: `tax_engine`, `app.py`

Scope:
- Expose intermediate values and assumptions for major calculations.
- Keep the trace structured enough for debugging and review.

UI:
- Add a `Calculation Trace` tab
- Group by:
  - income build-up
  - deductions
  - federal tax
  - provincial tax
  - refundable credits
  - refund/owing

Acceptance criteria:
- Major results can be explained line by line.
- Hidden inference points are easier to review.

### P3-04 Province modules and schedule modules hardening
Priority: Medium-High
Area: `tax_engine`

Scope:
- Continue the module split so provincial and schedule logic is easier to maintain.
- Reduce calculator-file sprawl.

Implementation:
- Move province-specific logic into per-province modules
- Move schedule logic into dedicated modules:
  - `schedule3.py`
  - `t776.py`
  - `t2209.py`
  - `schedule9.py`
  - `schedule11.py`

Acceptance criteria:
- New year updates can be made with less regression risk.
- Province logic is easier to test in isolation.

### P3-05 Automated regression test suite
Priority: Medium-High
Area: tests

Scope:
- Build test cases by tax year, province, and scenario.
- Add baseline examples for simple and complex returns.

Coverage:
- T4-only return
- T4 + RRSP
- T4 + T2202
- dividend-heavy return
- rental return
- foreign tax credit return
- family/dependant return
- donation carryforward return

Acceptance criteria:
- Core scenarios are reproducible across refactors.
- Year updates have a safety net.

### P3-06 Preparer-facing summary and export readiness
Priority: Medium
Area: `app.py`

Scope:
- Add review-oriented summaries for internal use.
- Prepare the app for future export or report generation.

UI:
- Add:
  - `Client Summary`
  - `Preparer Notes`
  - `Missing Information Checklist`

Acceptance criteria:
- The app is useful not only for calculation but also for review and client follow-up.

## Suggested Build Order
1. `P1-01 Full Schedule 3 engine`
2. `P1-02 Full T776 rental engine`
3. `P1-03 Stronger T2209 / T2036 foreign tax flow`
4. `P1-04 Complete Schedule 11 tuition and transfer flow`
5. `P1-06 Diagnostics and reconciliation v1`
6. `P2-01 Full household claim interaction engine`
7. `P2-02 Refundable credits engine`
8. `P2-05 Province-wide worksheet depth expansion`
9. `P3-02 Line-by-line return package`
10. `P3-05 Automated regression test suite`

## Definition of Near-Complete
Treat the app as near-complete only when all of these are true:
- Most common personal return scenarios can be entered through slips and guided forms without heavy manual approximation.
- Major federal and provincial credits are supported with visible worksheet logic.
- Return results are traceable line by line.
- Diagnostics catch common mistakes and missing inputs.
- Multi-year maintenance is practical because tax logic is modular and tested.
