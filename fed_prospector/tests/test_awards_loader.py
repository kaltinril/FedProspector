"""Tests for etl.awards_loader -- normalisation, composite keys, upsert logic."""

import pytest
from unittest.mock import MagicMock, patch

from etl.awards_loader import AwardsLoader, _make_composite_key, _AWARD_HASH_FIELDS


# ---------------------------------------------------------------------------
# Sample data builders
# ---------------------------------------------------------------------------
def _make_raw_award(**overrides):
    """Return a minimal raw SAM Contract Awards API dict."""
    base = {
        "contractId": {
            "piid": "  GS-35F-0001  ",
            "referencedIDVPiid": "GS-35F",
            "modificationNumber": "P00001",
            "transactionNumber": "0",
            "reasonForModification": {"code": "C"},
        },
        "coreData": {
            "federalOrganization": {
                "contractingInformation": {
                    "contractingDepartment": {"code": "4700", "name": "GSA"},
                    "contractingOffice": {"code": "47PA", "name": "PBS Region"},
                },
                "fundingInformation": {
                    "fundingDepartment": {"code": "4700", "name": "GSA"},
                    "fundingSubtier": {"code": "4740", "name": "Federal Acquisition Service"},
                },
            },
            "principalPlaceOfPerformance": {
                "state": {"code": "VA"},
                "country": {"code": "USA"},
                "zipCode": "22030",
            },
            "productOrServiceInformation": {
                "productOrService": {"code": "D301"},
                "principalNaics": [{"code": "541511"}],
            },
            "competitionInformation": {
                "typeOfSetAside": {"code": "WOSB"},
                "solicitationProcedures": {"code": "SP1"},
                "extentCompeted": {"code": "A", "name": "Full and Open Competition"},
            },
            "awardOrIDVType": {"code": "C"},
            "acquisitionData": {
                "typeOfContractPricing": {"code": "J"},
            },
            "solicitationId": "SOL-999",
            "solicitationDate": "2025-12-01",
        },
        "awardDetails": {
            "dates": {
                "dateSigned": "01/15/2026",
                "periodOfPerformanceStartDate": "2026-02-01",
                "currentCompletionDate": "2027-01-31",
                "ultimateCompletionDate": "2028-01-31",
            },
            "totalContractDollars": {
                "totalActionObligation": "500000.00",
                "totalBaseAndAllOptionsValue": "750000.00",
            },
            "competitionInformation": {
                "numberOfOffersReceived": 5,
            },
            "preferenceProgramsInformation": {
                "contractingOfficerBusinessSizeDetermination": [{"code": "S"}],
            },
            "productOrServiceInformation": {
                "descriptionOfContractRequirement": "IT Services",
            },
            "awardeeData": {
                "awardeeHeader": {"awardeeName": "Test Corp"},
                "awardeeUEIInformation": {"uniqueEntityId": "TESTAWARDEE1"},
                "far41102Exception": {"code": "1A", "name": "Statutory Exception"},
            },
            "transactionData": {
                "lastModifiedDate": "2026-01-20",
            },
        },
    }
    base.update(overrides)
    return base


# ===================================================================
# _make_composite_key tests
# ===================================================================

class TestMakeCompositeKey:

    def test_normal_key(self):
        assert _make_composite_key("CONT-1", "P00001") == "CONT-1|P00001"

    def test_none_modification_defaults_to_zero(self):
        assert _make_composite_key("CONT-1", None) == "CONT-1|0"

    def test_empty_modification_defaults_to_zero(self):
        assert _make_composite_key("CONT-1", "") == "CONT-1|0"


# ===================================================================
# _normalize_award tests
# ===================================================================

class TestNormalizeAward:

    def _loader(self):
        with patch("etl.awards_loader.get_connection"):
            return AwardsLoader()

    def test_normalize_basic_fields(self):
        loader = self._loader()
        result = loader._normalize_award(_make_raw_award())

        assert result["contract_id"] == "GS-35F-0001"
        assert result["idv_piid"] == "GS-35F"
        assert result["modification_number"] == "P00001"
        assert result["transaction_number"] == "0"

    def test_normalize_strips_whitespace(self):
        loader = self._loader()
        result = loader._normalize_award(_make_raw_award())
        # piid had leading/trailing spaces
        assert result["contract_id"] == "GS-35F-0001"

    def test_normalize_agency_info(self):
        loader = self._loader()
        result = loader._normalize_award(_make_raw_award())

        assert result["agency_id"] == "4700"
        assert result["agency_name"] == "GSA"
        assert result["contracting_office_id"] == "47PA"
        assert result["funding_agency_id"] == "4700"

    def test_normalize_pop(self):
        loader = self._loader()
        result = loader._normalize_award(_make_raw_award())

        assert result["pop_state"] == "VA"
        assert result["pop_country"] == "USA"
        assert result["pop_zip"] == "22030"

    def test_normalize_naics_from_list(self):
        loader = self._loader()
        result = loader._normalize_award(_make_raw_award())
        assert result["naics_code"] == "541511"

    def test_normalize_naics_from_dict(self):
        """NAICS can be a dict instead of a list in some responses."""
        loader = self._loader()
        raw = _make_raw_award()
        raw["coreData"]["productOrServiceInformation"]["principalNaics"] = {"code": "541512"}
        result = loader._normalize_award(raw)
        assert result["naics_code"] == "541512"

    def test_normalize_naics_empty_list(self):
        loader = self._loader()
        raw = _make_raw_award()
        raw["coreData"]["productOrServiceInformation"]["principalNaics"] = []
        result = loader._normalize_award(raw)
        assert result["naics_code"] is None

    def test_normalize_dates_mm_dd_yyyy(self):
        loader = self._loader()
        result = loader._normalize_award(_make_raw_award())
        assert result["date_signed"] == "2026-01-15"

    def test_normalize_dates_iso(self):
        loader = self._loader()
        result = loader._normalize_award(_make_raw_award())
        assert result["effective_date"] == "2026-02-01"

    def test_normalize_dollars(self):
        loader = self._loader()
        result = loader._normalize_award(_make_raw_award())
        assert result["dollars_obligated"] == "500000.00"
        assert result["base_and_all_options"] == "750000.00"

    def test_normalize_co_biz_size_from_list(self):
        loader = self._loader()
        result = loader._normalize_award(_make_raw_award())
        assert result["co_bus_size_determination"] == "S"

    def test_normalize_co_biz_size_from_dict(self):
        loader = self._loader()
        raw = _make_raw_award()
        raw["awardDetails"]["preferenceProgramsInformation"][
            "contractingOfficerBusinessSizeDetermination"
        ] = {"code": "O"}
        result = loader._normalize_award(raw)
        assert result["co_bus_size_determination"] == "O"

    def test_normalize_vendor_duns_always_none(self):
        loader = self._loader()
        result = loader._normalize_award(_make_raw_award())
        assert result["vendor_duns"] is None

    def test_normalize_extent_competed_from_extent_competed(self):
        """H1: extent_competed must read from extentCompeted, not solicitationProcedures."""
        loader = self._loader()
        result = loader._normalize_award(_make_raw_award())
        assert result["extent_competed"] == "A"

    def test_normalize_far_exception(self):
        """H2: far1102 exception must read from awardeeData.far41102Exception."""
        loader = self._loader()
        result = loader._normalize_award(_make_raw_award())
        assert result["far1102_exception_code"] == "1A"
        assert result["far1102_exception_name"] == "Statutory Exception"

    def test_normalize_far_exception_missing(self):
        """H2: far1102 exception fields should be None when absent."""
        loader = self._loader()
        raw = _make_raw_award()
        del raw["awardDetails"]["awardeeData"]["far41102Exception"]
        result = loader._normalize_award(raw)
        assert result["far1102_exception_code"] is None
        assert result["far1102_exception_name"] is None

    def test_normalize_funding_subtier(self):
        """M2: funding_subtier_code/name must map from fundingSubtier."""
        loader = self._loader()
        result = loader._normalize_award(_make_raw_award())
        assert result["funding_subtier_code"] == "4740"
        assert result["funding_subtier_name"] == "Federal Acquisition Service"

    def test_normalize_missing_core_blocks(self):
        """Empty raw dict should not crash, just return Nones."""
        loader = self._loader()
        result = loader._normalize_award({})
        assert result["contract_id"] is None
        assert result["agency_id"] is None


# ===================================================================
# Date parsing tests
# ===================================================================

class TestAwardsParseDate:

    def _loader(self):
        with patch("etl.awards_loader.get_connection"):
            return AwardsLoader()

    @pytest.mark.parametrize("input_val,expected", [
        ("2026-01-15", "2026-01-15"),
        ("01/15/2026", "2026-01-15"),
        ("2026-01-15T00:00:00", "2026-01-15"),
        (None, None),
        ("", None),
    ])
    def test_parse_date(self, input_val, expected):
        loader = self._loader()
        assert loader._parse_date(input_val) == expected


# ===================================================================
# Decimal parsing tests
# ===================================================================

class TestAwardsParseDecimal:

    def _loader(self):
        with patch("etl.awards_loader.get_connection"):
            return AwardsLoader()

    @pytest.mark.parametrize("input_val,expected", [
        ("500000.00", "500000.00"),
        (-25000, "-25000"),
        (None, None),
        ("garbage", None),
    ])
    def test_parse_decimal(self, input_val, expected):
        loader = self._loader()
        assert loader._parse_decimal(input_val) == expected


# ===================================================================
# Upsert outcome tests
# ===================================================================

class TestUpsertAward:

    def _loader(self):
        with patch("etl.awards_loader.get_connection"):
            return AwardsLoader()

    def test_upsert_inserted(self):
        loader = self._loader()
        cursor = MagicMock()
        cursor.rowcount = 1
        assert loader._upsert_award(cursor, {"contract_id": "C1"}, load_id=1) == "inserted"

    def test_upsert_updated(self):
        loader = self._loader()
        cursor = MagicMock()
        cursor.rowcount = 2
        assert loader._upsert_award(cursor, {"contract_id": "C1"}, load_id=1) == "updated"

    def test_upsert_unchanged(self):
        loader = self._loader()
        cursor = MagicMock()
        cursor.rowcount = 0
        assert loader._upsert_award(cursor, {"contract_id": "C1"}, load_id=1) == "unchanged"


# ===================================================================
# load_awards integration test (all DB mocked)
# ===================================================================

class TestLoadAwards:

    def test_new_award_inserted(self, mock_change_detector, mock_load_manager):
        mock_change_detector.compute_hash.return_value = "newhash"

        with patch("etl.awards_loader.get_connection") as mock_gc:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.rowcount = 1
            mock_conn.cursor.return_value = mock_cursor
            mock_gc.return_value = mock_conn

            loader = AwardsLoader(
                change_detector=mock_change_detector,
                load_manager=mock_load_manager,
            )
            stats = loader.load_awards([_make_raw_award()], load_id=1)

        assert stats["records_read"] == 1
        assert stats["records_inserted"] == 1
        assert stats["records_errored"] == 0

    def test_unchanged_award_skipped(self, mock_change_detector, mock_load_manager):
        mock_change_detector.compute_hash.return_value = "samehash"

        with patch("etl.awards_loader.get_connection") as mock_gc:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_gc.return_value = mock_conn

            loader = AwardsLoader(
                change_detector=mock_change_detector,
                load_manager=mock_load_manager,
            )
            # Pre-populate hash cache for the _get_existing_hashes call
            with patch.object(loader, "_get_existing_hashes",
                              return_value={"GS-35F-0001|P00001": "samehash"}):
                stats = loader.load_awards([_make_raw_award()], load_id=1)

        assert stats["records_unchanged"] == 1

    def test_missing_piid_counts_as_error(self, mock_change_detector, mock_load_manager):
        with patch("etl.awards_loader.get_connection") as mock_gc:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_gc.return_value = mock_conn

            loader = AwardsLoader(
                change_detector=mock_change_detector,
                load_manager=mock_load_manager,
            )
            bad_raw = {"contractId": {}, "coreData": {}, "awardDetails": {}}
            stats = loader.load_awards([bad_raw], load_id=1)

        assert stats["records_errored"] == 1


# ===================================================================
# Hash fields accessor
# ===================================================================

class TestAwardsGetHashFields:

    def test_returns_copy(self):
        fields = AwardsLoader.get_hash_fields()
        assert fields == list(_AWARD_HASH_FIELDS)
        fields.append("extra")
        assert "extra" not in _AWARD_HASH_FIELDS
