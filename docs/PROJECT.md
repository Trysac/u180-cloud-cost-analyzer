# Project Record

## Objective

Analyze FOCUS 1.0 cloud cost CSV exports with Decimal arithmetic: grouped totals by day or month, period comparison and tag coverage.

## Scope

- Parsing and validation of FOCUS 1.0 CSV files (ChargePeriodStart, EffectiveCost, BillingCurrency, ServiceName).
- Exact arithmetic calculations using `decimal.Decimal`.
- Support for `ServiceName`, `SubAccountId`, `RegionId`, `ChargeCategory`, `ProviderName`, and custom tag-based keys.
- Command-line interface for summarization, comparison, and coverage checks.

## Out-of-scope

- Provider-specific API integration or authentication.
- Automated currency conversion.
- Predictive forecasting or anomaly detection.
- Amortisation logic or complex financial modeling beyond raw FOCUS columns.

## Effort metrics

| Metric | Value |
|---|---|
| Tokens (input / output) | 655574 / 21457 |
| Hours (human) | pending measurement |
| Cost (USD) | 0.2094 |

## Factory run u180 (measured from API usage)

| Phase | Model | Batch | Input | Output | Cache write | Cache read | Cost (USD) |
|---|---|---|---|---|---|---|---|
| generation | gemini-3.8-flash | yes | 4661 | 14618 | 0 | 0 | 0.0292 |
| fix-1 | gemini-3.8-flash | no | 56801 | 3356 | 0 | 222229 | 0.0719 |
| fix-2 | gemini-3.8-flash | no | 18417 | 186 | 0 | 23971 | 0.0163 |
| fix-3 | gemini-3.8-flash | no | 25125 | 684 | 0 | 55437 | 0.0256 |
| fix-4 | gemini-3.8-flash | no | 18890 | 452 | 0 | 23958 | 0.0177 |
| audit | gemini-3.1-flash-lite | no | 30530 | 405 | 0 | 26470 | 0.0089 |
| docs | gemini-3.1-flash-lite | no | 149085 | 1756 | 0 | 0 | 0.0399 |

Total: $0.2094. Prices: Anthropic list prices.
