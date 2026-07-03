"""PII detection + masking — the privacy guarantee is gated here."""

import pandas as pd
import pytest

from analysis import pii


# --- fixtures -------------------------------------------------------------

RAW = {
    "email": "ravi.kumar@example.com",
    "pan": "ABCDE1234F",
    "aadhaar": "123456789012",
    "phone": "9876543210",
    "phone_intl": "+919876543210",
    "account": "123456789012345",
    "name": "Ravi Kumar",
}


def _df():
    return pd.DataFrame(
        {
            "customer_name": ["Ravi Kumar", "Sunita Rao", "Amit Shah", "Neha Verma"],
            "pan": ["ABCDE1234F", "PQRSX6789Z", "LMNOP4321Q", "ZYXWV1111A"],
            "aadhaar": ["123456789012", "234567890123", "345678901234", "456789012345"],
            "mobile": ["9876543210", "9812345678", "+919900112233", "9765432109"],
            "email_id": [
                "ravi.kumar@example.com",
                "sunita@bank.co.in",
                "amit.shah@test.org",
                "neha@mail.com",
            ],
            "acct_no": ["123456789012345", "223456789012345", "323456789012345", "423456789012345"],
            "principal": [100000, 250000, 75000, 500000],
            "dpd": [0, 95, 30, 120],
            "product": ["home", "auto", "home", "personal"],
        }
    )


# --- detection ------------------------------------------------------------

def test_detects_each_pii_type():
    detected = pii.detect_pii_columns(_df())
    assert detected["customer_name"] == "name"
    assert detected["pan"] == "pan"
    assert detected["aadhaar"] == "aadhaar"
    assert detected["mobile"] == "phone"
    assert detected["email_id"] == "email"
    assert detected["acct_no"] == "account"


def test_non_pii_columns_not_flagged():
    detected = pii.detect_pii_columns(_df())
    assert "principal" not in detected
    assert "dpd" not in detected
    assert "product" not in detected


def test_value_pattern_detection_without_helpful_column_names():
    # Columns named opaquely — detection must fall back to value patterns.
    df = pd.DataFrame(
        {
            "col_a": ["ABCDE1234F", "PQRSX6789Z", "LMNOP4321Q"],
            "col_b": ["ravi@example.com", "sunita@bank.in", "amit@test.org"],
            "col_c": [1, 2, 3],
        }
    )
    detected = pii.detect_pii_columns(df)
    assert detected.get("col_a") == "pan"
    assert detected.get("col_b") == "email"
    assert "col_c" not in detected


def test_company_column_not_false_positive_for_pan():
    # "company" contains the substring "pan" — must NOT be flagged as PAN.
    df = pd.DataFrame({"company": ["Acme Ltd", "Globex", "Initech"], "x": [1, 2, 3]})
    detected = pii.detect_pii_columns(df)
    assert "company" not in detected


# --- mask_schema ----------------------------------------------------------

def test_mask_schema_never_leaks_raw_pii():
    df = _df()
    out = pii.mask_schema(df)
    for raw in [
        "Ravi Kumar", "Sunita Rao",
        "ABCDE1234F", "PQRSX6789Z",
        "123456789012", "234567890123",
        "9876543210", "919900112233",
        "ravi.kumar@example.com", "sunita@bank.co.in",
        "123456789012345",
    ]:
        assert raw not in out, f"raw PII value leaked into schema: {raw}"


def test_mask_schema_keeps_non_pii_stats():
    out = pii.mask_schema(_df())
    # numeric stats for non-PII columns still present
    assert "principal" in out
    assert "dpd" in out
    assert "product" in out
    assert "Rows: 4" in out
    # a masked token is shown for PII columns
    assert "MASKED" in out


def test_mask_schema_does_not_dump_full_data():
    # 1000 rows — the schema must only sample a few, never dump all.
    df = pd.DataFrame({"email_id": [f"user{i}@x.com" for i in range(1000)], "v": range(1000)})
    out = pii.mask_schema(df)
    assert "user999@x.com" not in out
    assert out.count("MASKED") < 50  # only a small sample masked, not 1000 rows


# --- mask_result ----------------------------------------------------------

def test_mask_result_scalar_numeric_passes_through():
    assert pii.mask_result(123456.78) == "123456.78"


def test_mask_result_masks_pii_valued_frame():
    df = pd.DataFrame(
        {"name": ["Ravi Kumar", "Sunita Rao"], "total": [100, 200]}
    )
    out = pii.mask_result(df, {"name": "name"})
    assert "Ravi Kumar" not in out
    assert "Sunita Rao" not in out
    assert "MASKED" in out
    assert "100" in out and "200" in out  # non-PII numbers preserved


def test_mask_result_masks_pattern_pii_even_without_map():
    # A result surfacing an email/PAN with NO pii_map must still be masked.
    df = pd.DataFrame({"contact": ["ravi.kumar@example.com"], "n": [5]})
    out = pii.mask_result(df)  # no pii_map given
    assert "ravi.kumar@example.com" not in out
    assert "MASKED" in out


def test_mask_result_caps_rows():
    df = pd.DataFrame({"v": range(1000)})
    out = pii.mask_result(df)
    assert "truncated" in out
    assert "999" not in out


def test_mask_result_series_with_pii_index():
    # groupby on a name column -> PII appears in the index.
    s = pd.Series([10, 20], index=pd.Index(["Ravi Kumar", "Sunita Rao"], name="name"))
    out = pii.mask_result(s, {"name": "name"})
    assert "Ravi Kumar" not in out
    assert "Sunita Rao" not in out


def test_mask_result_none():
    assert pii.mask_result(None) == "None"
