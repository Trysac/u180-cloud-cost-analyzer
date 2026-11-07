# Stack

## Used

| Tool | Purpose |
|---|---|
| Python >= 3.10 | Standard library implementation for strict type safety and `Decimal` support. |
| uv | Environment and build management. |
| ruff | Linting and formatting. |
| pytest | Test execution. |

## Discarded

| Tool | Why not |
|---|---|
| Pandas / Polars | Overkill for a lightweight library; we prioritize zero runtime dependencies. |
| Complex build systems | The project is stdlib-only and requires minimal configuration.