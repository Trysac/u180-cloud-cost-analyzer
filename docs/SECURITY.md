# Security

## Threat Model

- **Denial of Service**: The library enforces hard limits on input to prevent resource exhaustion. Files larger than 50,000,000 bytes or containing more than 1,000,000 rows raise `CostError('input_too_large')`.
- **Data Integrity**: All monetary values are processed using `decimal.Decimal`. Invalid numeric strings or non-finite values (NaN, Inf) trigger `CostError('invalid_value')`.
- **Time Confusion**: The parser requires ISO 8601 datetimes with explicit offsets. Naive datetimes trigger `CostError('invalid_value')` to prevent timezone ambiguity.
- **Injection**: The utility does not use `eval` or `exec`. Tags are parsed via `json.loads` as a dictionary, and invalid JSON structures result in `CostError('invalid_value')`.