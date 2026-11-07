# cloud-cost-analyzer

[![PyPI version](https://img.shields.io/pypi/v/trysac-cloud-cost-analyzer)](https://pypi.org/project/trysac-cloud-cost-analyzer/)
[![License: MIT](https://img.shields.io/pypi/l/trysac-cloud-cost-analyzer)](LICENSE)
[![CI](https://github.com/Trysac/u180-cloud-cost-analyzer/actions/workflows/ci.yml/badge.svg)](https://github.com/Trysac/u180-cloud-cost-analyzer/actions/workflows/ci.yml)

Analyze FOCUS 1.0 cloud cost CSV exports with Decimal arithmetic: grouped totals by day or month, period comparison and tag coverage

## Problem

Describe in two or three sentences the concrete problem this utility solves, who hits it, and what
they do today without it. Replace this paragraph when the first real feature lands.

## Install

```sh
pip install trysac-cloud-cost-analyzer
# or
uv add trysac-cloud-cost-analyzer
```

Requires Python 3.10 or newer. No runtime dependencies.

## Usage

```python
import cloud_cost_analyzer

# normalize() trims surrounding whitespace and lower-cases the text.
print(cloud_cost_analyzer.normalize("  Hello World "))  # -> "hello world"

# Blank input is rejected explicitly instead of returning an empty string.
try:
    cloud_cost_analyzer.normalize("   ")
except ValueError as exc:
    print(f"rejected: {exc}")
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md) and [decisions](docs/decisions/)
- [Testing](docs/TESTING.md) and [security](docs/SECURITY.md)
- [Project record](docs/PROJECT.md) and [stack](docs/STACK.md)
- [Changelog](CHANGELOG.md) and [contributing guide](CONTRIBUTING.md)

## License

[MIT](LICENSE) (c) 2026 Miguel Gomez
