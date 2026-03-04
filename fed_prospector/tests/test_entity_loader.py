"""Tests for etl.entity_loader -- normalisation, child extraction, staging logic."""

import json
import pytest
from unittest.mock import MagicMock, patch, call

from etl.entity_loader import (
    EntityLoader,
    _ENTITY_HASH_FIELDS,
    _CHILD_KEY_COLUMNS,
    _safe_get,
    _str_or_none,
    _has_poc_data,
    _REG_STATUS_MAP,
)


# ---------------------------------------------------------------------------
# Sample data builders
# ---------------------------------------------------------------------------
def _make_raw_entity(**overrides):
    """Return a complete raw SAM.gov entity dict matching the API response structure."""
    base = {
        "entityRegistration": {
            "ueiSAM": "TESTABC12345",
            "ueiDUNS": "123456789",
            "cageCode": "1ABC2",
            "dodaac": None,
            "registrationStatus": "Active",
            "purposeOfRegistrationCode": "Z2",
            "registrationDate": "2020-01-15",
            "expirationDate": "2027-01-15",
            "lastUpdateDate": "2026-01-10",
            "activationDate": "2020-01-20",
            "legalBusinessName": "Test Federal Solutions LLC",
            "dbaName": "TestFed",
            "dnbOpenData": "Y",
            "correspondenceFlag": "M",
            "exclusionStatusFlag": "N",
            "noPublicDisplayFlag": "N",
            "evsSource": "E&Y",
        },
        "coreData": {
            "entityInformation": {
                "entityDivisionName": "IT Division",
                "entityDivisionNumber": "001",
                "entityStartDate": "2015-06-01",
                "fiscalYearEndCloseDate": "12/31",
                "entityURL": "https://testfed.com",
            },
            "generalInformation": {
                "entityStructureCode": "2J",
                "entityTypeCode": "F",
                "profitStructureCode": "2X",
                "organizationStructureCode": "XS",
                "stateOfIncorporationCode": "VA",
                "countryOfIncorporationCode": "USA",
            },
            "financialInformation": {
                "creditCardUsage": "Y",
                "debtSubjectToOffset": "N",
            },
            "physicalAddress": {
                "addressLine1": "123 Main St",
                "addressLine2": "Suite 100",
                "city": "Arlington",
                "stateOrProvinceCode": "VA",
                "zipCode": "22201",
                "zipCodePlus4": "1234",
                "countryCode": "USA",
                "congressionalDistrict": "08",
            },
            "mailingAddress": {
                "addressLine1": "PO Box 100",
                "city": "Arlington",
                "stateOrProvinceCode": "VA",
                "zipCode": "22201",
                "countryCode": "USA",
            },
            "businessTypes": {
                "businessTypeList": [
                    {"businessTypeCode": "8W", "businessTypeDescription": "WOSB"},
                    {"businessTypeCode": "27", "businessTypeDescription": "SB"},
                ],
                "sbaBusinessTypeList": [
                    {
                        "sbaBusinessTypeCode": "A4",
                        "sbaBusinessTypeDescription": "8(a)",
                        "certificationEntryDate": "2022-03-01",
                        "certificationExitDate": None,
                    }
                ],
            },
        },
        "assertions": {
            "goodsAndServices": {
                "primaryNaics": "541512",
                "naicsList": [
                    {"naicsCode": "541512", "sbaSmallBusiness": "Y", "naicsException": None},
                    {"naicsCode": "541511", "sbaSmallBusiness": "Y", "naicsException": None},
                ],
                "pscList": [
                    {"pscCode": "D301"},
                    {"pscCode": "D302"},
                ],
            },
            "disasterReliefData": {
                "geographicalAreaServed": [
                    {
                        "geographicalAreaServedStateCode": "VA",
                        "geographicalAreaServedStateName": "Virginia",
                        "geographicalAreaServedCountyCode": "013",
                        "geographicalAreaServedCountyName": "Arlington",
                    }
                ],
            },
        },
        "pointsOfContact": {
            "governmentBusinessPOC": {
                "firstName": "Jane",
                "lastName": "Doe",
                "title": "CEO",
                "addressLine1": "123 Main St",
                "city": "Arlington",
                "stateOrProvince": "VA",
                "zipCode": "22201",
                "countryCode": "USA",
            },
            "electronicBusinessPOC": {
                "firstName": "John",
                "lastName": "Smith",
            },
        },
    }
    base.update(overrides)
    return base


def _make_loader(change_detector=None, load_manager=None):
    """Create an EntityLoader with all DB connections mocked."""
    with patch("etl.entity_loader.get_connection"):
        return EntityLoader(
            change_detector=change_detector,
            load_manager=load_manager,
        )


# ===================================================================
# _normalize_entity tests
# ===================================================================

class TestNormalizeEntity:

    def test_normalize_complete_entity(self):
        """Verify all fields extracted from a complete entity dict."""
        loader = _make_loader()
        raw = _make_raw_entity()
        result = loader._normalize_entity(raw)

        assert result["uei_sam"] == "TESTABC12345"
        assert result["uei_duns"] == "123456789"
        assert result["cage_code"] == "1ABC2"
        assert result["dodaac"] is None
        assert result["registration_status"] == "A"
        assert result["purpose_of_registration"] == "Z2"
        assert result["initial_registration_date"] == "2020-01-15"
        assert result["registration_expiration_date"] == "2027-01-15"
        assert result["last_update_date"] == "2026-01-10"
        assert result["activation_date"] == "2020-01-20"
        assert result["legal_business_name"] == "Test Federal Solutions LLC"
        assert result["dba_name"] == "TestFed"
        assert result["entity_division"] == "IT Division"
        assert result["entity_division_number"] == "001"
        assert result["entity_start_date"] == "2015-06-01"
        assert result["fiscal_year_end_close"] == "12/31"
        assert result["entity_url"] == "https://testfed.com"
        assert result["entity_structure_code"] == "2J"
        assert result["entity_type_code"] == "F"
        assert result["profit_structure_code"] == "2X"
        assert result["organization_structure_code"] == "XS"
        assert result["state_of_incorporation"] == "VA"
        assert result["country_of_incorporation"] == "USA"
        assert result["primary_naics"] == "541512"
        assert result["credit_card_usage"] == "Y"
        assert result["correspondence_flag"] == "M"
        assert result["debt_subject_to_offset"] == "N"
        assert result["exclusion_status_flag"] == "N"
        assert result["no_public_display_flag"] == "N"
        assert result["evs_source"] == "E&Y"
        assert result["dnb_open_data_flag"] == "Y"

    def test_normalize_missing_optional_fields(self):
        """Verify no KeyError when optional blocks are missing."""
        loader = _make_loader()
        raw = {
            "entityRegistration": {
                "ueiSAM": "MINIMAL12345",
                "registrationStatus": "Active",
            },
        }
        result = loader._normalize_entity(raw)

        assert result["uei_sam"] == "MINIMAL12345"
        assert result["registration_status"] == "A"
        assert result["cage_code"] is None
        assert result["entity_division"] is None
        assert result["entity_structure_code"] is None
        assert result["primary_naics"] is None
        assert result["credit_card_usage"] is None

    def test_normalize_empty_entity(self):
        """Verify no crash on completely empty dict."""
        loader = _make_loader()
        result = loader._normalize_entity({})

        assert result["uei_sam"] is None
        assert result["registration_status"] is None
        assert result["legal_business_name"] is None

    def test_normalize_none_nested_dicts(self):
        """Verify no KeyError when nested blocks are None."""
        loader = _make_loader()
        raw = {
            "entityRegistration": None,
            "coreData": None,
            "assertions": None,
        }
        result = loader._normalize_entity(raw)

        assert result["uei_sam"] is None
        assert result["entity_structure_code"] is None

    def test_registration_status_mapping(self):
        """Verify all status text values are mapped correctly."""
        loader = _make_loader()
        for text, expected_code in _REG_STATUS_MAP.items():
            raw = {"entityRegistration": {"registrationStatus": text}}
            result = loader._normalize_entity(raw)
            assert result["registration_status"] == expected_code

    def test_unknown_registration_status_first_char(self):
        """Unknown status text should use first char."""
        loader = _make_loader()
        raw = {"entityRegistration": {"registrationStatus": "Pending"}}
        result = loader._normalize_entity(raw)
        assert result["registration_status"] == "P"


# ===================================================================
# _extract_child_records tests
# ===================================================================

class TestExtractChildRecords:

    def test_extract_all_child_types(self):
        """Complete entity should produce rows for all child tables."""
        loader = _make_loader()
        raw = _make_raw_entity()
        children = loader._extract_child_records(raw, "TESTABC12345")

        assert len(children["entity_address"]) == 2  # physical + mailing
        assert len(children["entity_naics"]) == 2
        assert len(children["entity_psc"]) == 2
        assert len(children["entity_business_type"]) == 2
        assert len(children["entity_sba_certification"]) == 1
        assert len(children["entity_poc"]) == 2  # govBiz + eBiz
        assert len(children["entity_disaster_response"]) == 1

    def test_extract_address_types(self):
        loader = _make_loader()
        raw = _make_raw_entity()
        children = loader._extract_child_records(raw, "TESTABC12345")
        addrs = children["entity_address"]

        physical = next(a for a in addrs if a["address_type"] == "PHYSICAL")
        mailing = next(a for a in addrs if a["address_type"] == "MAILING")

        assert physical["city"] == "Arlington"
        assert physical["state_or_province"] == "VA"
        assert physical["congressional_district"] == "08"
        assert mailing["address_line_1"] == "PO Box 100"

    def test_extract_naics_primary_flag(self):
        loader = _make_loader()
        raw = _make_raw_entity()
        children = loader._extract_child_records(raw, "TESTABC12345")
        naics = children["entity_naics"]

        primary = next(n for n in naics if n["naics_code"] == "541512")
        secondary = next(n for n in naics if n["naics_code"] == "541511")

        assert primary["is_primary"] == "Y"
        assert secondary["is_primary"] == "N"

    def test_extract_poc_types(self):
        loader = _make_loader()
        raw = _make_raw_entity()
        children = loader._extract_child_records(raw, "TESTABC12345")
        pocs = children["entity_poc"]

        types = [p["poc_type"] for p in pocs]
        assert "governmentBusinessPOC" in types
        assert "electronicBusinessPOC" in types

    def test_extract_empty_entity(self):
        """No children should be produced from empty dict."""
        loader = _make_loader()
        children = loader._extract_child_records({}, "EMPTY123")

        for table_name, rows in children.items():
            assert isinstance(rows, list)
            assert len(rows) == 0, f"Expected 0 rows for {table_name}"

    def test_extract_sba_certification_dates(self):
        loader = _make_loader()
        raw = _make_raw_entity()
        children = loader._extract_child_records(raw, "TESTABC12345")
        sba = children["entity_sba_certification"]

        assert len(sba) == 1
        assert sba[0]["sba_type_code"] == "A4"
        assert sba[0]["certification_entry_date"] == "2022-03-01"
        assert sba[0]["certification_exit_date"] is None

    def test_extract_uei_sam_set_on_all_children(self):
        """Every child row should have the parent uei_sam."""
        loader = _make_loader()
        raw = _make_raw_entity()
        children = loader._extract_child_records(raw, "MY_UEI")

        for table_name, rows in children.items():
            for row in rows:
                assert row["uei_sam"] == "MY_UEI", f"Missing uei_sam in {table_name}"


# ===================================================================
# _sync_child_records tests
# ===================================================================

class TestSyncChildRecords:

    def test_sync_empty_records_only_deletes(self):
        """When new_records is empty, DELETE should run but no INSERT."""
        loader = _make_loader()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        loader._sync_child_records(
            mock_conn, mock_cursor, "UEI123", "entity_naics", [], []
        )

        # Should delete existing rows
        mock_cursor.execute.assert_called_once()
        assert "DELETE" in mock_cursor.execute.call_args[0][0]
        # Should NOT call executemany (no insert)
        mock_cursor.executemany.assert_not_called()

    def test_sync_nonempty_records_deletes_and_inserts(self):
        """Non-empty records should trigger DELETE then INSERT."""
        loader = _make_loader()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        records = [
            {"uei_sam": "UEI123", "naics_code": "541512", "is_primary": "Y"},
        ]

        loader._sync_child_records(
            mock_conn, mock_cursor, "UEI123", "entity_naics", records,
            ["uei_sam", "naics_code"]
        )

        # Should have DELETE call
        delete_call = mock_cursor.execute.call_args_list[0]
        assert "DELETE" in delete_call[0][0]

        # Should have INSERT via executemany
        mock_cursor.executemany.assert_called_once()
        insert_sql = mock_cursor.executemany.call_args[0][0]
        assert "INSERT" in insert_sql


# ===================================================================
# _process_entities tests
# ===================================================================

class TestProcessEntities:

    def test_process_write_staging_false_no_staging_connection(self):
        """write_staging=False should NOT open a staging connection."""
        mock_cd = MagicMock()
        mock_cd.get_existing_hashes.return_value = {}
        mock_cd.compute_hash.return_value = "hash123"
        mock_lm = MagicMock()

        with patch("etl.entity_loader.get_connection") as mock_gc:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.rowcount = 1  # inserted
            mock_cursor.fetchone.return_value = None
            mock_conn.cursor.return_value = mock_cursor
            mock_gc.return_value = mock_conn

            loader = EntityLoader(
                change_detector=mock_cd,
                load_manager=mock_lm,
            )
            raw = _make_raw_entity()
            stats = loader._process_entities(iter([raw]), load_id=1, write_staging=False)

        assert stats["records_read"] == 1
        assert stats["records_inserted"] == 1
        # get_connection should be called once for the main connection only
        # (write_staging=False means no staging connection)
        assert mock_gc.call_count == 1

    def test_process_write_staging_true_opens_staging_connection(self):
        """write_staging=True should open a second connection for staging."""
        mock_cd = MagicMock()
        mock_cd.get_existing_hashes.return_value = {}
        mock_cd.compute_hash.return_value = "hash123"
        mock_lm = MagicMock()

        with patch("etl.entity_loader.get_connection") as mock_gc:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.rowcount = 1
            mock_cursor.fetchone.return_value = None
            mock_conn.cursor.return_value = mock_cursor
            mock_gc.return_value = mock_conn

            loader = EntityLoader(
                change_detector=mock_cd,
                load_manager=mock_lm,
            )
            raw = _make_raw_entity()
            stats = loader._process_entities(iter([raw]), load_id=1, write_staging=True)

        assert stats["records_read"] == 1
        # get_connection called twice: staging + main
        assert mock_gc.call_count == 2


# ===================================================================
# load_from_json_extract tests
# ===================================================================

class TestLoadFromJsonExtract:

    def test_calls_stream_and_process(self):
        """Verify it wires up the streaming, processing, and load management."""
        mock_cd = MagicMock()
        mock_cd.get_existing_hashes.return_value = {}
        mock_cd.compute_hash.return_value = "hash"
        mock_lm = MagicMock()
        mock_lm.start_load.return_value = 42
        mock_dc = MagicMock()
        mock_dc.reset_stats.return_value = None
        mock_dc.get_stats.return_value = {}

        with patch("etl.entity_loader.get_connection") as mock_gc:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.rowcount = 1
            mock_cursor.fetchone.return_value = None
            mock_conn.cursor.return_value = mock_cursor
            mock_gc.return_value = mock_conn

            loader = EntityLoader(
                change_detector=mock_cd,
                data_cleaner=mock_dc,
                load_manager=mock_lm,
            )
            # Patch the streaming to return a simple list
            with patch.object(loader, "_stream_json_file", return_value=iter([_make_raw_entity()])):
                stats = loader.load_from_json_extract("/fake/path.json")

        assert stats["records_read"] == 1
        mock_lm.start_load.assert_called_once()
        mock_lm.complete_load.assert_called_once()
        # Staging should NOT be written (JSON extract path)
        assert mock_gc.call_count == 1


# ===================================================================
# load_from_api_response tests
# ===================================================================

class TestLoadFromApiResponse:

    def test_calls_staging_write(self):
        """API response path should use write_staging=True."""
        mock_cd = MagicMock()
        mock_cd.get_existing_hashes.return_value = {}
        mock_cd.compute_hash.return_value = "hash"
        mock_lm = MagicMock()
        mock_lm.start_load.return_value = 99

        with patch("etl.entity_loader.get_connection") as mock_gc:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.rowcount = 1
            mock_cursor.fetchone.return_value = None
            mock_conn.cursor.return_value = mock_cursor
            mock_gc.return_value = mock_conn

            loader = EntityLoader(
                change_detector=mock_cd,
                load_manager=mock_lm,
            )
            stats = loader.load_from_api_response([_make_raw_entity()])

        assert stats["records_read"] == 1
        # get_connection called twice: staging + main
        assert mock_gc.call_count == 2
        mock_lm.complete_load.assert_called_once()


# ===================================================================
# Module-level helper tests
# ===================================================================

class TestSafeGet:

    def test_dict_with_key(self):
        assert _safe_get({"a": 1}, "a") == 1

    def test_dict_missing_key(self):
        assert _safe_get({"a": 1}, "b") is None

    def test_none_input(self):
        assert _safe_get(None, "a") is None

    def test_non_dict_input(self):
        assert _safe_get([1, 2, 3], "a") is None


class TestStrOrNone:

    def test_none_returns_none(self):
        assert _str_or_none(None) is None

    def test_string_returns_string(self):
        assert _str_or_none("hello") == "hello"

    def test_int_returns_string(self):
        assert _str_or_none(42) == "42"


class TestHasPocData:

    def test_has_first_name(self):
        assert _has_poc_data({"firstName": "Jane"}) is True

    def test_has_last_name(self):
        assert _has_poc_data({"lastName": "Doe"}) is True

    def test_empty_poc(self):
        assert _has_poc_data({}) is False

    def test_only_address(self):
        assert _has_poc_data({"city": "Arlington"}) is False


# ===================================================================
# Hash fields accessor
# ===================================================================

class TestEntityHashFields:

    def test_returns_copy(self):
        fields = EntityLoader._get_entity_hash_fields()
        assert fields == list(_ENTITY_HASH_FIELDS)
        fields.append("extra")
        assert "extra" not in _ENTITY_HASH_FIELDS
