"""cloud_cost_analyzer: FinOps FOCUS 1.0 CSV cost analyzer with exact Decimal arithmetic."""

from __future__ import annotations

import csv
import io
import json
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation
from typing import Any, Literal

__all__ = [
    "CostError",
    "CostGroup",
    "CostRow",
    "Coverage",
    "Delta",
    "__version__",
    "compare",
    "load_focus_csv",
    "render",
    "summarize",
    "tag_coverage",
]

__version__ = "0.1.0"

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

ErrorCode = Literal[
    "input_too_large",
    "missing_column",
    "invalid_value",
    "currency_mismatch",
    "invalid_option",
]

STANDARD_DIMENSIONS: dict[str, str] = {
    "ServiceName": "service",
    "SubAccountId": "sub_account",
    "RegionId": "region",
    "ChargeCategory": "charge_category",
    "ProviderName": "provider",
}


class CostError(Exception):
    """Base exception for all cloud_cost_analyzer errors with a typed machine-readable code."""

    def __init__(self, code: ErrorCode, message: str) -> None:
        super().__init__(message)
        self.code: ErrorCode = code
        self.message: str = message

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True)
class CostRow:
    """Represents a single parsed FOCUS cost row."""

    period_start: datetime
    service: str
    sub_account: str
    region: str
    charge_category: str
    provider: str
    cost: Decimal
    currency: str
    tags: Mapping[str, str]


@dataclass(frozen=True)
class CostGroup:
    """Represents aggregate cost grouped by a period and a key."""

    period: str
    key: str
    cost: Decimal


@dataclass(frozen=True)
class Delta:
    """Represents cost change between two periods for a specific key."""

    key: str
    previous: Decimal
    current: Decimal
    change: Decimal
    change_pct: Decimal | None


@dataclass(frozen=True)
class Coverage:
    """Represents tag allocation coverage summary."""

    tagged: Decimal
    untagged: Decimal
    untagged_share: Decimal


def _truncate(val: Any, limit: int = 200) -> str:
    s = str(val)
    return s if len(s) <= limit else s[:limit]


def _parse_iso_utc(date_str: str, row_num: int) -> datetime:
    cleaned = date_str.strip()
    if not cleaned:
        raise CostError(
            "invalid_value",
            f"Empty ChargePeriodStart at row {row_num}",
        )
    iso_text = cleaned
    if iso_text.endswith("Z") or iso_text.endswith("z"):
        iso_text = iso_text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(iso_text)
    except Exception as exc:
        raise CostError(
            "invalid_value",
            f"Invalid datetime '{_truncate(cleaned)}' at row {row_num}",
        ) from exc
    if dt.tzinfo is None:
        raise CostError(
            "invalid_value",
            f"Naive datetime without timezone offset '{_truncate(cleaned)}' at row {row_num}",
        )
    return dt.astimezone(timezone.utc)


def load_focus_csv(
    text: str,
    *,
    cost_column: str = "EffectiveCost",
    max_bytes: int = 50_000_000,
    max_rows: int = 1_000_000,
) -> list[CostRow]:
    """Parse a FOCUS 1.0 CSV export into a list of CostRow objects."""
    text_bytes_len = len(text.encode("utf-8"))
    if text_bytes_len > max_bytes:
        raise CostError(
            "input_too_large",
            f"Input size {text_bytes_len} bytes exceeds maximum allowed {max_bytes} bytes",
        )

    cleaned_text = text.lstrip("\ufeff")
    reader = csv.reader(io.StringIO(cleaned_text))

    try:
        header = next(reader)
    except StopIteration:
        return []

    col_to_idx: dict[str, int] = {}
    for idx, col in enumerate(header):
        col_name = col.strip()
        if col_name and col_name not in col_to_idx:
            col_to_idx[col_name] = idx

    required_cols = ["ChargePeriodStart", cost_column, "BillingCurrency", "ServiceName"]
    for req in required_cols:
        if req not in col_to_idx:
            raise CostError(
                "missing_column",
                f"Missing required column '{req}' in CSV header (row 1)",
            )

    period_idx = col_to_idx["ChargePeriodStart"]
    cost_idx = col_to_idx[cost_column]
    currency_idx = col_to_idx["BillingCurrency"]
    service_idx = col_to_idx["ServiceName"]
    sub_account_idx = col_to_idx.get("SubAccountId")
    region_idx = col_to_idx.get("RegionId")
    category_idx = col_to_idx.get("ChargeCategory")
    provider_idx = col_to_idx.get("ProviderName")
    tags_idx = col_to_idx.get("Tags")

    rows: list[CostRow] = []
    row_count = 0

    for line_idx, raw_row in enumerate(reader, start=2):
        if not raw_row or (len(raw_row) == 1 and raw_row[0].strip() == ""):
            continue

        row_count += 1
        if row_count > max_rows:
            raise CostError(
                "input_too_large",
                f"Row count exceeds maximum allowed limit of {max_rows} rows at row {line_idx}",
            )

        def get_val(row: list[str], idx: int | None) -> str:
            if idx is None or idx >= len(row):
                return ""
            return row[idx].strip()

        period_str = get_val(raw_row, period_idx)
        dt = _parse_iso_utc(period_str, line_idx)

        cost_str = get_val(raw_row, cost_idx)
        if not cost_str:
            raise CostError(
                "invalid_value",
                f"Empty cost value for column '{cost_column}' at row {line_idx}",
            )
        lower_cost = cost_str.lower()
        if lower_cost in {"nan", "inf", "+inf", "-inf", "infinity", "+infinity", "-infinity"}:
            raise CostError(
                "invalid_value",
                f"Invalid cost value '{_truncate(cost_str)}' at row {line_idx}",
            )
        try:
            cost_dec = Decimal(cost_str)
            if not cost_dec.is_finite():
                raise CostError(
                    "invalid_value",
                    f"Non-finite cost value '{_truncate(cost_str)}' at row {line_idx}",
                )
        except (InvalidOperation, ValueError) as exc:
            raise CostError(
                "invalid_value",
                f"Invalid numeric cost value '{_truncate(cost_str)}' at row {line_idx}",
            ) from exc

        currency = get_val(raw_row, currency_idx)
        if not currency:
            raise CostError(
                "invalid_value",
                f"Missing BillingCurrency at row {line_idx}",
            )

        service = get_val(raw_row, service_idx)
        sub_account = get_val(raw_row, sub_account_idx)
        region = get_val(raw_row, region_idx)
        charge_cat = get_val(raw_row, category_idx)
        provider = get_val(raw_row, provider_idx)

        tags_raw = get_val(raw_row, tags_idx)
        tags_dict: dict[str, str] = {}
        if tags_raw:
            try:
                parsed_tags = json.loads(tags_raw)
                if not isinstance(parsed_tags, dict):
                    raise ValueError("Tags is not a JSON object")
                tags_dict = {str(k): str(v) for k, v in parsed_tags.items()}
            except Exception as exc:
                raise CostError(
                    "invalid_value",
                    f"Invalid JSON tags '{_truncate(tags_raw)}' at row {line_idx}",
                ) from exc

        rows.append(
            CostRow(
                period_start=dt,
                service=service,
                sub_account=sub_account,
                region=region,
                charge_category=charge_cat,
                provider=provider,
                cost=cost_dec,
                currency=currency,
                tags=tags_dict,
            )
        )

    return rows


def _ensure_consistent_currency(rows: Sequence[CostRow]) -> str:
    if not rows:
        return ""
    first_currency = rows[0].currency
    for idx, r in enumerate(rows, start=1):
        if r.currency != first_currency:
            raise CostError(
                "currency_mismatch",
                f"Conflicting currencies: found '{r.currency}' at row {idx + 1} "
                f"differing from '{first_currency}'",
            )
    return first_currency


def _extract_key(row: CostRow, by: str) -> str:
    if by.startswith("tag:"):
        tag_name = by[4:]
        return row.tags.get(tag_name, "(untagged)")
    if by in STANDARD_DIMENSIONS:
        attr = STANDARD_DIMENSIONS[by]
        val = getattr(row, attr)
        return str(val)
    raise CostError(
        "invalid_option",
        f"Unsupported dimension '{_truncate(by)}'. "
        f"Expected one of {list(STANDARD_DIMENSIONS.keys())} or 'tag:<name>'",
    )


def summarize(
    rows: Sequence[CostRow],
    *,
    by: str,
    granularity: Literal["day", "month"] = "month",
) -> list[CostGroup]:
    """Group costs by period and key, returning a list of CostGroup sorted by period then key."""
    if granularity not in ("day", "month"):
        raise CostError(
            "invalid_option",
            f"Invalid granularity '{granularity}'. Expected 'day' or 'month'",
        )
    _ensure_consistent_currency(rows)
    if not rows:
        _extract_key(
            CostRow(
                period_start=datetime.now(timezone.utc),
                service="",
                sub_account="",
                region="",
                charge_category="",
                provider="",
                cost=Decimal("0"),
                currency="USD",
                tags={},
            ),
            by,
        )
        return []

    grouped: dict[tuple[str, str], Decimal] = {}
    for row in rows:
        if granularity == "month":
            period_key = row.period_start.strftime("%Y-%m")
        else:
            period_key = row.period_start.strftime("%Y-%m-%d")
        key = _extract_key(row, by)
        pair = (period_key, key)
        grouped[pair] = grouped.get(pair, Decimal("0")) + row.cost

    sorted_keys = sorted(grouped.keys(), key=lambda x: (x[0], x[1]))
    return [CostGroup(period=p, key=k, cost=grouped[(p, k)]) for p, k in sorted_keys]


def compare(
    rows: Sequence[CostRow],
    *,
    by: str,
    current: str,
    previous: str,
) -> list[Delta]:
    """Compare costs between two periods (e.g. YYYY-MM or YYYY-MM-DD) across all keys."""
    _ensure_consistent_currency(rows)
    is_day_cur = len(current) == 10 and current[4] == "-" and current[7] == "-"
    is_day_prev = len(previous) == 10 and previous[4] == "-" and previous[7] == "-"
    granularity: Literal["day", "month"] = "day" if (is_day_cur or is_day_prev) else "month"

    # Validate 'by' early
    if not rows:
        _extract_key(
            CostRow(
                period_start=datetime.now(timezone.utc),
                service="",
                sub_account="",
                region="",
                charge_category="",
                provider="",
                cost=Decimal("0"),
                currency="USD",
                tags={},
            ),
            by,
        )

    prev_totals: dict[str, Decimal] = {}
    curr_totals: dict[str, Decimal] = {}
    all_keys: set[str] = set()

    for row in rows:
        if granularity == "day":
            row_period = row.period_start.strftime("%Y-%m-%d")
        else:
            row_period = row.period_start.strftime("%Y-%m")
        key = _extract_key(row, by)
        if row_period == previous:
            prev_totals[key] = prev_totals.get(key, Decimal("0")) + row.cost
            all_keys.add(key)
        elif row_period == current:
            curr_totals[key] = curr_totals.get(key, Decimal("0")) + row.cost
            all_keys.add(key)

    deltas: list[Delta] = []
    for k in all_keys:
        prev_val = prev_totals.get(k, Decimal("0"))
        curr_val = curr_totals.get(k, Decimal("0"))
        change = curr_val - prev_val
        change_pct: Decimal | None
        if prev_val == Decimal("0"):
            change_pct = None
        else:
            raw_pct = (change / prev_val) * Decimal("100")
            change_pct = raw_pct.quantize(Decimal("0.1"), rounding=ROUND_HALF_EVEN)
        deltas.append(
            Delta(
                key=k,
                previous=prev_val,
                current=curr_val,
                change=change,
                change_pct=change_pct,
            )
        )

    deltas.sort(key=lambda d: (-abs(d.change), d.key))
    return deltas


def tag_coverage(rows: Sequence[CostRow], key: str) -> Coverage:
    """Calculate total tagged cost, untagged cost, and untagged share for a given tag key."""
    _ensure_consistent_currency(rows)
    tagged = Decimal("0")
    untagged = Decimal("0")

    for r in rows:
        if key in r.tags and r.tags[key] != "":
            tagged += r.cost
        else:
            untagged += r.cost

    total = tagged + untagged
    if total == Decimal("0"):
        share = Decimal("0")
    else:
        raw_share = untagged / total
        share = raw_share.quantize(Decimal("0.0001"), rounding=ROUND_HALF_EVEN)

    return Coverage(tagged=tagged, untagged=untagged, untagged_share=share)


def render(items: Sequence[CostGroup] | Sequence[Delta], fmt: Literal["csv", "text"]) -> str:
    """Render CostGroup or Delta items into formatted CSV or aligned plain text."""
    if fmt not in ("csv", "text"):
        raise CostError(
            "invalid_option",
            f"Invalid render format '{fmt}'. Expected 'csv' or 'text'",
        )

    if not items:
        return ""

    first = items[0]
    if isinstance(first, CostGroup):
        groups: Sequence[CostGroup] = items  # type: ignore[assignment]
        if fmt == "csv":
            out = io.StringIO()
            writer = csv.writer(out, lineterminator="\r\n")
            writer.writerow(["period", "key", "cost"])
            for g in groups:
                c_str = str(g.cost.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN))
                writer.writerow([g.period, g.key, c_str])
            return out.getvalue()
        else:
            rows_text = [
                [
                    g.period,
                    g.key,
                    str(g.cost.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)),
                ]
                for g in groups
            ]
            headers = ["period", "key", "cost"]
            w_period = max(len(headers[0]), max(len(r[0]) for r in rows_text))
            w_key = max(len(headers[1]), max(len(r[1]) for r in rows_text))
            w_cost = max(len(headers[2]), max(len(r[2]) for r in rows_text))

            lines = [
                f"{headers[0]:<{w_period}}  {headers[1]:<{w_key}}  {headers[2]:>{w_cost}}",
                f"{'=' * w_period}  {'=' * w_key}  {'=' * w_cost}",
            ]
            for p, k, c in rows_text:
                lines.append(f"{p:<{w_period}}  {k:<{w_key}}  {c:>{w_cost}}")
            return "\n".join(lines)

    elif isinstance(first, Delta):
        deltas: Sequence[Delta] = items  # type: ignore[assignment]
        if fmt == "csv":
            out = io.StringIO()
            writer = csv.writer(out, lineterminator="\r\n")
            writer.writerow(["key", "previous", "current", "change", "change_pct"])
            for d in deltas:
                prev_str = str(d.previous.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN))
                curr_str = str(d.current.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN))
                chg_str = str(d.change.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN))
                pct_str = "" if d.change_pct is None else str(d.change_pct)
                writer.writerow([d.key, prev_str, curr_str, chg_str, pct_str])
            return out.getvalue()
        else:
            rows_text = [
                [
                    d.key,
                    str(d.previous.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)),
                    str(d.current.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)),
                    str(d.change.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)),
                    "-" if d.change_pct is None else f"{d.change_pct}%",
                ]
                for d in deltas
            ]
            headers = ["key", "previous", "current", "change", "change_pct"]
            col_widths = [max(len(headers[i]), max(len(r[i]) for r in rows_text)) for i in range(5)]
            hdr_line = "  ".join(
                f"{headers[i]:<{col_widths[i]}}" if i == 0 else f"{headers[i]:>{col_widths[i]}}"
                for i in range(5)
            )
            sep_line = "  ".join("=" * col_widths[i] for i in range(5))
            lines = [hdr_line, sep_line]
            for r in rows_text:
                row_line = "  ".join(
                    f"{r[i]:<{col_widths[i]}}" if i == 0 else f"{r[i]:>{col_widths[i]}}"
                    for i in range(5)
                )
                lines.append(row_line)
            return "\n".join(lines)

    return ""
