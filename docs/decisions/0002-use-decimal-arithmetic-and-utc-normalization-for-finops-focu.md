# Use Decimal Arithmetic and UTC Normalization for FinOps FOCUS Analysis

Status: accepted (generated, pending human review)

## Context

FinOps practitioners require exact cost accounting when analyzing FOCUS 1.0 cloud billing CSV exports. Standard floating point introduces precision drift and cumulative rounding errors across large datasets. Furthermore, billing records originate in varied timezones and ISO 8601 notations that must be normalized to UTC.

## Decision

Implement load_focus_csv, summarize, compare, and tag_coverage using Decimal values exclusively for monetary values without intermediate rounding. Normalize all ChargePeriodStart timestamps into aware UTC datetimes, supporting trailing 'Z' on Python 3.10+, and enforce strict currency consistency and input size limits.

## Consequences

Calculations are completely deterministic and offline with zero runtime dependencies. Aggregation errors are eliminated, invalid dates and mixed currencies are detected early, and output formatting cleanly quantizes values to standard decimal display places.
