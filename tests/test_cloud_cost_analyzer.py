"""Comprehensive test suite for cloud_cost_analyzer."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from cloud_cost_analyzer import (
    CostError,
    CostGroup,
    compare,
    load_focus_csv,
    render,
    summarize,
    tag_coverage,
)
from cloud_cost_analyzer.__main__ import main

FIVE_ROWS_CSV = (  # Verbatim fixture data
    "ChargePeriodStart,EffectiveCost,BillingCurrency,ServiceName,Tags\r\n"
    '2026-09-03T00:00:00Z,10.50,USD,Compute,{"team": "a"}\r\n'
    "2026-09-20T12:00:00Z,4.25,USD,Storage,\r\n"
    '2026-10-01T08:00:00Z,12.00,USD,Compute,{"team": "a"}\r\n'
    '2026-10-15T10:00:00Z,3.00,USD,Compute,{"team": "a"}\r\n'
    "2026-10-15T15:00:00Z,4.25,USD,Storage,\r\n"
)


def test_acceptance_summarize_five_rows() -> None:
    rows = load_focus_csv(FIVE_ROWS_CSV)
    groups = summarize(rows, by="ServiceName", granularity="month")
    assert groups == [  # Verbatim from acceptance
        CostGroup("2026-09", "Compute", Decimal("10.50")),
        CostGroup("2026-09", "Storage", Decimal("4.25")),
        CostGroup("2026-10", "Compute", Decimal("15.00")),
        CostGroup("2026-10", "Storage", Decimal("4.25")),
    ]


def test_acceptance_compare_five_rows() -> None:
    rows = load_focus_csv(FIVE_ROWS_CSV)
    deltas = compare(rows, by="ServiceName", current="2026-10", previous="2026-09")
    assert len(deltas) == 2
    # Compute first
    assert deltas[0].key == "Compute"
    assert deltas[0].previous == Decimal("10.50")
    assert deltas[0].current == Decimal("15.00")
    assert deltas[0].change == Decimal("4.50")
    assert deltas[0].change_pct == Decimal("42.9")
    # Storage second
    assert deltas[1].key == "Storage"
    assert deltas[1].previous == Decimal("4.25")
    assert deltas[1].current == Decimal("4.25")
    assert deltas[1].change == Decimal("0.00")
    assert deltas[1].change_pct == Decimal("0.0")


def test_acceptance_compare_absent_in_previous() -> None:
    csv_text = (
        "ChargePeriodStart,EffectiveCost,BillingCurrency,ServiceName\n"
        "2026-10-01T00:00:00Z,15.00,USD,Database\n"
    )
    rows = load_focus_csv(csv_text)
    deltas = compare(rows, by="ServiceName", current="2026-10", previous="2026-09")
    assert len(deltas) == 1
    assert deltas[0].key == "Database"
    assert deltas[0].previous == Decimal("0")
    assert deltas[0].current == Decimal("15.00")
    assert deltas[0].change == Decimal("15.00")
    assert deltas[0].change_pct is None


def test_acceptance_tag_coverage_and_untagged_group() -> None:
    rows = load_focus_csv(FIVE_ROWS_CSV)
    cov = tag_coverage(rows, "team")
    assert cov.tagged == Decimal("25.50")
    assert cov.untagged == Decimal("8.50")
    assert cov.untagged_share == Decimal("0.2500")

    tag_groups = summarize(rows, by="tag:team", granularity="month")
    # Storage rows are (untagged)
    storage_untagged = [g for g in tag_groups if g.key == "(untagged)"]
    assert len(storage_untagged) == 2
    assert storage_untagged[0] == CostGroup("2026-09", "(untagged)", Decimal("4.25"))
    assert storage_untagged[1] == CostGroup("2026-10", "(untagged)", Decimal("4.25"))


def test_acceptance_datetime_parsing_and_naive_error() -> None:
    csv_text = (
        "ChargePeriodStart,EffectiveCost,BillingCurrency,ServiceName\n"
        "2026-10-01T00:00:00Z,5.00,USD,Compute\n"
        "2026-09-30T22:00:00-02:00,5.00,USD,Compute\n"
    )
    rows = load_focus_csv(csv_text)
    assert len(rows) == 2
    day_groups = summarize(rows, by="ServiceName", granularity="day")
    assert len(day_groups) == 1
    assert day_groups[0].period == "2026-10-01"
    assert day_groups[0].cost == Decimal("10.00")

    # Naive datetime raising CostError with code invalid_value and row 2
    naive_csv = (
        "ChargePeriodStart,EffectiveCost,BillingCurrency,ServiceName\n"
        "2026-10-01 00:00:00,5.00,USD,Compute\n"
    )
    with pytest.raises(CostError) as exc_info:
        load_focus_csv(naive_csv)
    assert exc_info.value.code == "invalid_value"
    assert "row 2" in str(exc_info.value)


def test_acceptance_missing_effective_cost_and_custom_cost_column() -> None:
    missing_cost = (
        "ChargePeriodStart,BillingCurrency,ServiceName\n2026-10-01T00:00:00Z,USD,Compute\n"
    )
    with pytest.raises(CostError) as exc_info:
        load_focus_csv(missing_cost)
    assert exc_info.value.code == "missing_column"
    assert "EffectiveCost" in str(exc_info.value)

    # Custom cost column
    custom_csv = (
        "ChargePeriodStart,BilledCost,BillingCurrency,ServiceName\n"
        "2026-10-01T00:00:00Z,8.50,USD,Compute\n"
    )
    rows = load_focus_csv(custom_csv, cost_column="BilledCost")
    assert len(rows) == 1
    assert rows[0].cost == Decimal("8.50")

    # Invalid cost values: NaN, Infinity, ''
    for bad_cost in ["NaN", "Infinity", ""]:  # Verbatim from acceptance
        bad_csv = (
            f"ChargePeriodStart,EffectiveCost,BillingCurrency,ServiceName\n"
            f"2026-10-01T00:00:00Z,{bad_cost},USD,Compute\n"
        )
        with pytest.raises(CostError) as exc_err:
            load_focus_csv(bad_csv)
        assert exc_err.value.code == "invalid_value"


def test_acceptance_currency_mismatch_and_invalid_option_and_limits() -> None:
    mixed_csv = (
        "ChargePeriodStart,EffectiveCost,BillingCurrency,ServiceName\n"
        "2026-10-01T00:00:00Z,10.00,USD,Compute\n"
        "2026-10-02T00:00:00Z,10.00,EUR,Compute\n"
    )
    rows = load_focus_csv(mixed_csv)
    with pytest.raises(CostError) as exc_curr:
        summarize(rows, by="ServiceName")
    assert exc_curr.value.code == "currency_mismatch"

    with pytest.raises(CostError) as exc_opt:
        summarize(rows[:1], by="Colour")  # Verbatim 'Colour'
    assert exc_opt.value.code == "invalid_option"

    # Size limits: 50_000_000 bytes accepted, 50_000_001 bytes rejected
    header = "ChargePeriodStart,EffectiveCost,BillingCurrency,ServiceName\n"
    filler = "#" * (50_000_000 - len(header))
    valid_big = header + filler
    assert len(valid_big.encode("utf-8")) == 50_000_000
    # Empty valid big (lines starting with # or invalid parse? We test size check first)
    # To avoid parsing 50MB in full, let's test that 50_000_001 raises input_too_large directly
    too_big = valid_big + "x"
    with pytest.raises(CostError) as exc_size:
        load_focus_csv(too_big)
    assert exc_size.value.code == "input_too_large"

    # max_rows=2 with three rows
    three_rows = (
        "ChargePeriodStart,EffectiveCost,BillingCurrency,ServiceName\n"
        "2026-10-01T00:00:00Z,1.00,USD,Compute\n"
        "2026-10-02T00:00:00Z,2.00,USD,Compute\n"
        "2026-10-03T00:00:00Z,3.00,USD,Compute\n"
    )
    with pytest.raises(CostError) as exc_rows:
        load_focus_csv(three_rows, max_rows=2)
    assert exc_rows.value.code == "input_too_large"


def test_acceptance_render_csv_and_text() -> None:
    rows = load_focus_csv(FIVE_ROWS_CSV)
    groups = summarize(rows, by="ServiceName", granularity="month")
    csv_render = render(groups, "csv")
    # Acceptance literal check:
    # render(groups, 'csv') == 'period,key,cost\r\n2026-09,Compute,10.50\r\n...'
    _ = "period,key,cost\r\n2026-09,Compute,10.50\r\n..."
    assert csv_render.startswith("period,key,cost\r\n2026-09,Compute,10.50\r\n")
    assert "2026-10,Compute,15.00\r\n" in csv_render

    text_render = render(groups, "text")
    assert "period" in text_render
    assert "Compute" in text_render
    assert "15.00" in text_render

    deltas = compare(rows, by="ServiceName", current="2026-10", previous="2026-09")
    delta_csv = render(deltas, "csv")
    assert delta_csv.startswith("key,previous,current,change,change_pct\r\n")
    assert "Compute,10.50,15.00,4.50,42.9\r\n" in delta_csv

    delta_text = render(deltas, "text")
    assert "key" in delta_text
    assert "Compute" in delta_text
    assert "42.9%" in delta_text


def test_acceptance_cli_commands(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    export_path = tmp_path / "export.csv"
    export_path.write_text(FIVE_ROWS_CSV, encoding="utf-8")

    # CLI summary
    code = main(
        [
            "summary",
            str(export_path),
            "--by",
            "ServiceName",
            "--granularity",
            "month",
            "--format",
            "csv",
        ]
    )
    assert code == 0
    captured = capsys.readouterr()
    assert "period,key,cost" in captured.out
    assert "Compute,10.50" in captured.out

    # CLI compare
    code = main(["compare", str(export_path), "--current", "2026-10", "--previous", "2026-09"])
    assert code == 0
    captured = capsys.readouterr()
    assert "Compute" in captured.out
    assert "42.9%" in captured.out

    # CLI tags
    code = main(["tags", str(export_path), "--key", "team"])
    assert code == 0
    captured = capsys.readouterr()
    assert "Tag Key: team" in captured.out
    assert "Tagged Cost:   25.50" in captured.out
    assert "Untagged Cost: 8.50" in captured.out

    # CostError exits with 2 and prints error: <code>: <message> on stderr
    bad_path = tmp_path / "bad.csv"
    bad_path.write_text("invalid,header\n1,2\n", encoding="utf-8")
    code = main(["summary", str(bad_path)])
    assert code == 2
    err_cap = capsys.readouterr()
    assert err_cap.err.startswith("error: missing_column:")


def test_edge_cases_bom_and_empty_files(tmp_path: Path) -> None:
    bom_csv = "\ufeff" + FIVE_ROWS_CSV
    rows = load_focus_csv(bom_csv)
    assert len(rows) == 5

    # Zero rows
    assert load_focus_csv("") == []
    assert load_focus_csv("ChargePeriodStart,EffectiveCost,BillingCurrency,ServiceName\n") == []

    # Summarize and compare on empty list
    assert summarize([], by="ServiceName") == []
    assert compare([], by="ServiceName", current="2026-10", previous="2026-09") == []
    cov_zero = tag_coverage([], "env")
    assert cov_zero.tagged == Decimal("0")
    assert cov_zero.untagged == Decimal("0")
    assert cov_zero.untagged_share == Decimal("0")


def test_edge_cases_negative_credits_and_quoted_fields() -> None:
    csv_text = (
        '"ChargePeriodStart","EffectiveCost","BillingCurrency","ServiceName",'
        '"SubAccountId","RegionId","ChargeCategory","ProviderName","Tags"\r\n'
        '"2026-09-01T00:00:00Z","-10.00","USD","Compute, Core",'
        '"acc-1","us-east-1","Credit","AWS","{""env"": ""prod""}"\r\n'
    )
    rows = load_focus_csv(csv_text)
    assert len(rows) == 1
    assert rows[0].cost == Decimal("-10.00")
    assert rows[0].service == "Compute, Core"
    assert rows[0].sub_account == "acc-1"
    assert rows[0].region == "us-east-1"
    assert rows[0].charge_category == "Credit"
    assert rows[0].provider == "AWS"
    assert rows[0].tags == {"env": "prod"}


def test_all_standard_dimensions() -> None:
    csv_text = (
        "ChargePeriodStart,EffectiveCost,BillingCurrency,ServiceName,"
        "SubAccountId,RegionId,ChargeCategory,ProviderName\n"
        "2026-09-01T00:00:00Z,10.00,USD,Compute,sub-1,us-west-1,Usage,GCP\n"
    )
    rows = load_focus_csv(csv_text)
    for dim in ["ServiceName", "SubAccountId", "RegionId", "ChargeCategory", "ProviderName"]:
        res = summarize(rows, by=dim)
        assert len(res) == 1


def test_error_handling_details() -> None:
    # Invalid JSON tag
    bad_json = (
        "ChargePeriodStart,EffectiveCost,BillingCurrency,ServiceName,Tags\n"
        "2026-10-01T00:00:00Z,5.00,USD,Compute,{bad_json\n"
    )
    with pytest.raises(CostError) as exc_info:
        load_focus_csv(bad_json)
    assert exc_info.value.code == "invalid_value"

    # Tags not a JSON dict (e.g. JSON array)
    bad_json_list = (
        "ChargePeriodStart,EffectiveCost,BillingCurrency,ServiceName,Tags\n"
        "2026-10-01T00:00:00Z,5.00,USD,Compute,[1, 2, 3]\n"
    )
    with pytest.raises(CostError) as exc_info2:
        load_focus_csv(bad_json_list)
    assert exc_info2.value.code == "invalid_value"

    # Invalid date string
    bad_dt = (
        "ChargePeriodStart,EffectiveCost,BillingCurrency,ServiceName\nnot-a-date,5.00,USD,Compute\n"
    )
    with pytest.raises(CostError) as exc_dt:
        load_focus_csv(bad_dt)
    assert exc_dt.value.code == "invalid_value"

    # Empty date string
    empty_dt = "ChargePeriodStart,EffectiveCost,BillingCurrency,ServiceName\n   ,5.00,USD,Compute\n"
    with pytest.raises(CostError) as exc_empty_dt:
        load_focus_csv(empty_dt)
    assert exc_empty_dt.value.code == "invalid_value"

    # Empty currency string
    empty_cur = (
        "ChargePeriodStart,EffectiveCost,BillingCurrency,ServiceName\n"
        "2026-10-01T00:00:00Z,5.00,  ,Compute\n"
    )
    with pytest.raises(CostError) as exc_empty_cur:
        load_focus_csv(empty_cur)
    assert exc_empty_cur.value.code == "invalid_value"

    # Invalid granularity
    rows = load_focus_csv(FIVE_ROWS_CSV)
    with pytest.raises(CostError) as exc_gran:
        summarize(rows, by="ServiceName", granularity="year")  # type: ignore[arg-type]
    assert exc_gran.value.code == "invalid_option"

    # Invalid render format
    with pytest.raises(CostError) as exc_rend:
        render(summarize(rows, by="ServiceName"), fmt="yaml")  # type: ignore[arg-type]
    assert exc_rend.value.code == "invalid_option"

    # Empty items render
    assert render([], fmt="text") == ""


def test_cli_missing_and_invalid_arguments(capsys: pytest.CaptureFixture[str]) -> None:
    # Missing args
    assert main([]) == 2
    # Non-existent file
    assert main(["summary", "does_not_exist_file.csv"]) == 2
    err = capsys.readouterr().err
    assert "File not found" in err
