# Architecture

`cloud-cost-analyzer` acts as a library and CLI tool for local analysis of FinOps FOCUS 1.0 datasets.

## Components

- **Parser**: Converts raw CSV strings to `CostRow` objects. Performs strict validation of FOCUS column requirements (`ChargePeriodStart`, `EffectiveCost`, `BillingCurrency`, `ServiceName`).
- **Analyzer**: Contains pure functions (`summarize`, `compare`, `tag_coverage`) for data transformation using `decimal.Decimal`.
- **Renderer**: Formats analytical results (`CostGroup`, `Delta`) into aligned text or CSV format, applying quantization (`ROUND_HALF_EVEN`) only at the final display stage.
- **CLI**: A wrapper around the library, routing commands (`summary`, `compare`, `tags`) to specific API endpoints and handling OS errors/system exits.