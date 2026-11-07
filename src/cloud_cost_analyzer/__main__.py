"""CLI entry point for cloud_cost_analyzer."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path

from cloud_cost_analyzer import (
    CostError,
    compare,
    load_focus_csv,
    render,
    summarize,
    tag_coverage,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cloud_cost_analyzer",
        description="FinOps FOCUS 1.0 Cloud Cost Analyzer CLI",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # summary subcommand
    summary_p = subparsers.add_parser("summary", help="Summarize costs grouped by a dimension")
    summary_p.add_argument("file", type=str, help="Path to FOCUS CSV file")
    summary_p.add_argument(
        "--by",
        type=str,
        default="ServiceName",
        help=(
            "Grouping dimension: ServiceName, SubAccountId, RegionId, "
            "ChargeCategory, ProviderName, or tag:<key>"
        ),
    )
    summary_p.add_argument(
        "--granularity",
        type=str,
        choices=["month", "day"],
        default="month",
        help="Time granularity (month or day)",
    )
    summary_p.add_argument(
        "--format",
        type=str,
        choices=["text", "csv"],
        default="text",
        help="Output format (text or csv)",
    )
    summary_p.add_argument(
        "--cost-column",
        type=str,
        default="EffectiveCost",
        help="Cost column name (default: EffectiveCost)",
    )

    # compare subcommand
    compare_p = subparsers.add_parser("compare", help="Compare costs between two periods")
    compare_p.add_argument("file", type=str, help="Path to FOCUS CSV file")
    compare_p.add_argument(
        "--by",
        type=str,
        default="ServiceName",
        help="Grouping dimension",
    )
    compare_p.add_argument(
        "--current",
        type=str,
        required=True,
        help="Current period (YYYY-MM or YYYY-MM-DD)",
    )
    compare_p.add_argument(
        "--previous",
        type=str,
        required=True,
        help="Previous period (YYYY-MM or YYYY-MM-DD)",
    )
    compare_p.add_argument(
        "--format",
        type=str,
        choices=["text", "csv"],
        default="text",
        help="Output format (text or csv)",
    )
    compare_p.add_argument(
        "--cost-column",
        type=str,
        default="EffectiveCost",
        help="Cost column name (default: EffectiveCost)",
    )

    # tags subcommand
    tags_p = subparsers.add_parser("tags", help="Show allocation coverage for a tag key")
    tags_p.add_argument("file", type=str, help="Path to FOCUS CSV file")
    tags_p.add_argument("--key", type=str, required=True, help="Tag key to check coverage for")
    tags_p.add_argument(
        "--cost-column",
        type=str,
        default="EffectiveCost",
        help="Cost column name (default: EffectiveCost)",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Main CLI entrypoint."""
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        # Exit code 2 for usage errors / argument parsing failure
        code = exc.code
        if code is None or code == 0:
            return 0
        return 2

    try:
        file_path = Path(args.file)
        if not file_path.exists():
            sys.stderr.write(f"error: invalid_value: File not found: {args.file}\n")
            return 2
        content = file_path.read_text(encoding="utf-8")
        rows = load_focus_csv(content, cost_column=args.cost_column)

        if args.command == "summary":
            groups = summarize(rows, by=args.by, granularity=args.granularity)
            rendered = render(groups, fmt=args.format)
            if rendered:
                sys.stdout.write(rendered + ("\n" if not rendered.endswith("\n") else ""))
            return 0

        elif args.command == "compare":
            deltas = compare(rows, by=args.by, current=args.current, previous=args.previous)
            rendered = render(deltas, fmt=args.format)
            if rendered:
                sys.stdout.write(rendered + ("\n" if not rendered.endswith("\n") else ""))
            return 0

        elif args.command == "tags":
            cov = tag_coverage(rows, key=args.key)
            tagged_str = str(cov.tagged.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN))
            untagged_str = str(cov.untagged.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN))
            share_pct = (cov.untagged_share * Decimal("100")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_EVEN
            )
            sys.stdout.write(
                f"Tag Key: {args.key}\n"
                f"Tagged Cost:   {tagged_str}\n"
                f"Untagged Cost: {untagged_str}\n"
                f"Untagged Share: {cov.untagged_share} ({share_pct}%)\n"
            )
            return 0

        return 0
    except CostError as exc:
        sys.stderr.write(f"error: {exc.code}: {exc.message}\n")
        return 2
    except OSError as exc:
        sys.stderr.write(f"error: invalid_value: I/O error: {exc}\n")
        return 2


if __name__ == "__main__":
    sys.exit(main())
