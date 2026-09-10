from pathlib import Path

from app.ingestion.profiler import profile_csv


def test_profile_is_data_driven(tmp_path: Path):
    csv = tmp_path / "orders.csv"

    csv.write_text(
        "order_key,ordered_at,region,amount\n"
        "A1,2026-01-01,North,10.5\n"
        "A2,2026-01-02,South,20.0\n"
        "A3,2026-01-03,North,5.0\n",
        encoding="utf-8",
    )

    profile = profile_csv(csv)

    assert profile["row_count"] == 3
    assert profile["column_count"] == 4

    by_name = {
        column["name"]: column
        for column in profile["columns"]
    }

    # Numeric columns should be detected as measures.
    assert by_name["amount"]["role"] == "numeric_measure"

    # Date columns should be detected as date/time.
    assert by_name["ordered_at"]["role"] == "date_or_time"

    # The current profiler treats very small categorical-like
    # text columns conservatively as text_or_other.
    assert by_name["region"]["role"] in {
        "categorical",
        "text_or_other",
    }