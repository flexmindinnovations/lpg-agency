from __future__ import annotations

from datetime import date

from lpg.domain.customer.kyc_document_parser import parse_kyc_document


class TestParseKycDocument:
    def test_extracts_aadhaar_number_name_and_dob_from_clean_text(self) -> None:
        result = parse_kyc_document(
            "Government of India\nRAMESH KUMAR\nDOB: 15/01/1990\nMALE\n1234 5678 9012"
        )

        assert result.doc_type == "aadhaar"
        assert result.document_number == "123456789012"
        assert result.full_name == "RAMESH KUMAR"
        assert result.date_of_birth == date(1990, 1, 15)

    def test_extracts_pan_number_and_document_type(self) -> None:
        result = parse_kyc_document(
            "INCOME TAX DEPARTMENT\nGOVT. OF INDIA\nRAMESH KUMAR\nABCDE1234F"
        )

        assert result.doc_type == "pan"
        assert result.document_number == "ABCDE1234F"

    def test_does_not_mistake_short_ocr_noise_for_a_name(self) -> None:
        # Reproduces a real misread: single-letter and vowel-less garbage
        # tokens that a bare "looks like letters" check would wrongly accept.
        result = parse_kyc_document("w\nCE ww Aw\nDOB: 30/05/1995\n1234 5678 9012")

        assert result.full_name is None
        assert result.date_of_birth == date(1995, 5, 30)

    def test_does_not_let_aadhaar_match_span_a_line_break(self) -> None:
        # The trailing "1995" from the DOB line plus the true Aadhaar
        # digits on the next line together happen to form a 12-digit run —
        # must not be accepted as the document number.
        result = parse_kyc_document("SUNITA VERMA\nDOB: 30/05/1995\n1234 5678 9012")

        assert result.document_number == "123456789012"

    def test_returns_nulls_when_no_supported_document_is_recognized(self) -> None:
        result = parse_kyc_document("just some random unrelated text")

        assert result.doc_type is None
        assert result.document_number is None

    def test_prefers_the_name_line_immediately_before_the_dob_line(self) -> None:
        result = parse_kyc_document(
            "Government of India\nSome Header Noise Line\nSUNITA VERMA\n"
            "DOB: 12/03/1988\n1234 5678 9012"
        )

        assert result.full_name == "SUNITA VERMA"

    def test_ignores_the_aadhaar_issued_date_and_extracts_the_real_dob(self) -> None:
        # Reproduces a real misread: "Aadhaar no. issued: 24/08/2011" is
        # printed on the card before the actual "DOB: 30/05/1995" line, and
        # both are the same DD/MM/YYYY shape — a bare "first date in the
        # text" search wrongly picks the issued date as the date of birth.
        result = parse_kyc_document(
            "Aadhaar no. issued: 24/08/2011\nVilas Rakhe\n"
            "DOB: 30/05/1995\nMALE\n7730 0889 2163"
        )

        assert result.date_of_birth == date(1995, 5, 30)
        assert result.full_name == "Vilas Rakhe"

    def test_parses_a_real_aadhaar_address_block_into_structured_fields(self) -> None:
        # Real card layout: a standalone "Address:" label followed by
        # freeform, multi-line text with "PO:"/"DIST:" labels and a
        # trailing "State - PINCODE" line, then the Aadhaar number repeats.
        result = parse_kyc_document(
            "Aadhaar no. issued: 24/08/2011\nVilas Rakhe\nDOB: 30/05/1995\nMALE\n"
            "7730 0889 2163\n"
            "Address:\n"
            "ROW H.n. 2 sonal nagar Opp. chavan saheb home,\n"
            "Subhadra Niwas near railway station, Jalna, PO: Jalna,\n"
            "DIST: Jalna,\n"
            "Maharashtra - 431203\n"
            "7730 0889 2163\n"
            "VID: 9186 7890 6417 0314"
        )

        assert result.address is not None
        assert result.address.line_1 == "ROW H.n. 2 sonal nagar Opp. chavan saheb home"
        assert result.address.city == "Jalna"
        assert result.address.district == "Jalna"
        assert result.address.state == "Maharashtra"
        assert result.address.pincode == "431203"
        assert result.address.landmark == "railway station"

    def test_returns_no_address_when_the_document_has_no_address_block(self) -> None:
        result = parse_kyc_document(
            "INCOME TAX DEPARTMENT\nGOVT. OF INDIA\nRAMESH KUMAR\nABCDE1234F"
        )

        assert result.address is None
