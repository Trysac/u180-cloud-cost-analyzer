# cloud-cost-analyzer

Analyze FinOps FOCUS 1.0 cloud cost CSV exports offline using exact Python `Decimal` arithmetic.

## Overview

Cloud bills arrive as large CSV exports that finance and engineering teams open in spreadsheets, where floating-point sums drift, mixed currencies blend unnoticed, and untagged cloud spend stays invisible. The FinOps Foundation's **FOCUS 1.0** (FinOps Open Cost and Usage Specification) defines an open standard for cloud billing datasets across AWS, Azure, Google Cloud, and OCI.

`cloud-cost-analyzer` provides a clean, dependency-free, standard-library-only Python engine and CLI to analyze FOCUS 1.0 datasets without loss of precision:
- **Exact Decimal totals**: Never uses float arithmetic, avoiding floating-point rounding errors.
- **Temporal grouping**: Aggregates costs by day or month across core dimensions (`ServiceName`, `SubAccountId`, `RegionId`, `ChargeCategory`, `ProviderName`, or arbitrary tags via `tag:<key>`).
- **Period comparison**: Calculates exact changes and percentage deltas between periods.
- **Tag coverage**: Quantifies tagged versus untagged expenditure and coverage ratio.
- **CLI & Formatted output**: Tabular aligned text or CSV output for reports and automation.

## Installation

```bash
pip install cloud-cost-analyzer
```

## Usage

```python
from cloud_cost_analyzer import load_focus_csv, summarize, render

rows = load_focus_csv(open("focus.csv").read())
groups = summarize(rows, by="ServiceName", granularity="month")
print(render(groups, fmt="text"))
```

## Public API Summary

- `load_focus_csv`: Parses FOCUS 1.0 CSVs. Errors: `input_too_large` (>50MB or >1M rows), `missing_column`, `invalid_value` (non-finite costs, bad datetimes, naive datetimes). Optional `cost_column` override.
- `summarize`: Aggregates cost by period and key. Errors: `invalid_option` (granularity), `currency_mismatch`.
- `compare`: Deltas between periods. Errors: `currency_mismatch`.
- `tag_coverage`: Calculates allocation ratio.
- `render`: Exports to 'text' or 'csv'.

## Why not existing SaaS tools?

FinOps tools are typically hosted SaaS products; this provides a standard library, offline-first tool for FOCUS datasets, ensuring data privacy and exact arithmetic.

## Security

See [docs/SECURITY.md](docs/SECURITY.md).