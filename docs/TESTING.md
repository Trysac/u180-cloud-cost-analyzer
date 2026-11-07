# Testing

## Overview

The project uses a standard test layout mirroring the source modules. Tests are deterministic and avoid network I/O.

- `tests/test_cloud_cost_analyzer.py`: Validates the primary parsing, aggregation, and arithmetic logic. 
- **Coverage**: The test suite covers the public API, ensuring `load_focus_csv` handles valid and invalid headers, `summarize` and `compare` perform calculations correctly according to acceptance criteria, and `tag_coverage` accurately identifies untagged spend.
- **Validation**: Includes tests for the `CostError` codes (`input_too_large`, `missing_column`, `invalid_value`, `currency_mismatch`, `invalid_option`).