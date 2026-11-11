"""Prévia da EFD-Reinf R-4000 (ADR 032): conferência dos pagamentos, id, valores, agrupamento e XSD oficial.

Todos os documentos são fictícios, com dígitos verificadores calculados.
"""

from __future__ import annotations

import hashlib
import io
import re
import zipfile
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from lxml import etree

from contabil.platform.clock import BRASILIA
from contabil.platform.errors import DomainError
from contabil.regulatory.registry import reinf_natures
from contabil.regulatory.reinf_preview import (
    DSIG,
    EVENTS,
    XSD_DIR,
    Responsible,
    build_events,
    event_id,
    format_value,
    group_payments,
    package,
    payment_issues,
    preview_file_name,
    readme_text,
    validate_events,
    xsd_errors,
)
from contabil.seed.cnpj import cnpj_digits
from contabil.seed.cpf import cpf_digits
from contabil.withholdings.validators import CleanPayment, PaymentInput, payment_problems, validate_payment

DECLARANT = cnpj_digits("123456780001")
SUPPLIER = cnpj_digits("112223330001")
OTHER_SUPPLIER = cnpj_digits("445556660001")
PERSON = cpf_digits("123456789")
ALPHANUMERIC = "12ABC34501DE35"
START, END = date(2026, 10, 1), date(2026, 10, 31)
GENERATED = datetime(2026, 11, 11, 12, 0, 0, tzinfo=BRASILIA)
OFFICIAL_SHA256 = {
    "R-4010-evt4010PagtoBeneficiarioPF-v2_01_02.xsd": "1117909497a6bcd93b0ce633aa51d793f075944bc1f85fcacafc9b28262fd357",
    "R-4020-evt4020PagtoBeneficiarioPJ-v2_01_02.xsd": "39da69e212d97dcb8f75e6c9fc8b41924eb461c4b2fcac18b14088d9f269793f",
    "R-4099-evt4099FechamentoDirf-v2_01_02.xsd": "d770a5cf3c6301477e8fafbc315a2ced23d89840730924143b61e6ba4c654a51",
}


def _input(**overrides) -> PaymentInput:
    base = {
        "beneficiary_kind": "pj",
        "beneficiary_document": SUPPLIER,
        "beneficiary_name": "Consultoria Fictícia Ltda.",
        "nature_code": "15014",
        "payment_date": "2026-10-20",
        "gross_amount": "10000.00",
        "ir_base": "10000.00",
        "ir_amount": "150.00",
        "csrf_base": "10000.00",
        "csrf_amount": "465.00",
        "description": None,
    }
    base.update(overrides)
    return PaymentInput(**base)


def _check(**overrides):
    return payment_problems(_input(**overrides), period_start=START, period_end=END)


def _locs(errors: list[dict]) -> set[str]:
    return {error["loc"][0] for error in errors}


def _payment(**overrides) -> CleanPayment:
    clean, errors = _check(**overrides)
    assert not errors, errors
    assert clean is not None
    return clean


def _person(**overrides) -> CleanPayment:
    base = {
        "beneficiary_kind": "pf",
        "beneficiary_document": PERSON,
        "beneficiary_name": "Locador Fictício",
        "nature_code": "13002",
        "payment_date": "2026-10-05",
        "gross_amount": "6000.00",
        "ir_base": "6000.00",
        "ir_amount": "1000.00",
        "csrf_base": None,
        "csrf_amount": None,
    }
    base.update(overrides)
    return _payment(**base)


# Conferência do pagamento


def test_a_valid_company_payment_is_normalized() -> None:
    masked = f"{SUPPLIER[:2]}.{SUPPLIER[2:5]}.{SUPPLIER[5:8]}/{SUPPLIER[8:12]}-{SUPPLIER[12:]}"
    clean = _payment(beneficiary_document=masked, beneficiary_name="  Consultoria   Fictícia ", gross_amount="10000.5")
    assert clean.beneficiary_document == SUPPLIER
    assert clean.beneficiary_name == "Consultoria Fictícia"
    assert clean.gross_amount == Decimal("10000.50")
    assert clean.payment_date == date(2026, 10, 20)


def test_the_alphanumeric_cnpj_is_accepted_in_upper_case() -> None:
    clean = _payment(beneficiary_document="12.abc.345/01de-35")
    assert clean.beneficiary_document == ALPHANUMERIC


@pytest.mark.parametrize(
    ("overrides", "loc"),
    [
        ({"beneficiary_document": SUPPLIER[:-1] + str((int(SUPPLIER[-1]) + 1) % 10)}, "beneficiary_document"),
        ({"beneficiary_kind": "pf", "beneficiary_document": "123.456.789-00", "nature_code": "13002", "csrf_base": None, "csrf_amount": None}, "beneficiary_document"),
        ({"beneficiary_kind": "pf", "beneficiary_document": "1234567890A", "nature_code": "13002", "csrf_base": None, "csrf_amount": None}, "beneficiary_document"),
        ({"beneficiary_kind": "xx"}, "beneficiary_kind"),
        ({"beneficiary_name": "   "}, "beneficiary_name"),
        ({"beneficiary_name": "x" * 151}, "beneficiary_name"),
        ({"nature_code": "1501"}, "nature_code"),
        ({"nature_code": "17099"}, "nature_code"),
        ({"nature_code": "13002"}, "nature_code"),
        ({"payment_date": "2026-11-01"}, "payment_date"),
        ({"payment_date": "20/10/2026"}, "payment_date"),
        ({"gross_amount": "0.00"}, "gross_amount"),
        ({"gross_amount": "10,00"}, "gross_amount"),
        ({"gross_amount": "1.005"}, "gross_amount"),
        ({"gross_amount": None}, "gross_amount"),
        ({"ir_base": "100.00", "ir_amount": "150.00"}, "ir_amount"),
        ({"ir_base": None, "ir_amount": "15.00"}, "ir_base"),
        ({"csrf_base": "100.00", "csrf_amount": "465.00"}, "csrf_amount"),
        ({"csrf_base": None, "csrf_amount": "4.65"}, "csrf_base"),
        ({"description": "x" * 201}, "description"),
    ],
)
def test_each_wrong_field_is_reported_by_name(overrides: dict, loc: str) -> None:
    clean, errors = _check(**overrides)
    assert clean is None
    assert loc in _locs(errors), errors


def test_person_payment_has_no_csrf_and_base_up_to_gross() -> None:
    _, errors = payment_problems(
        _input(beneficiary_kind="pf", beneficiary_document=PERSON, nature_code="13002", csrf_base="100.00", csrf_amount=None),
        period_start=START,
        period_end=END,
    )
    assert "csrf_base" in _locs(errors)
    _, errors = payment_problems(
        _input(beneficiary_kind="pf", beneficiary_document=PERSON, nature_code="10002", gross_amount="100.00", ir_base="150.00", ir_amount=None, csrf_base=None, csrf_amount=None),
        period_start=START,
        period_end=END,
    )
    assert _locs(errors) == {"ir_base"}


def test_ir_waived_keeps_the_base_without_amount() -> None:
    clean = _payment(gross_amount="500.00", ir_base="500.00", ir_amount=None, csrf_base="500.00", csrf_amount=None)
    assert clean.ir_base == Decimal("500.00") and clean.ir_amount is None


def test_validate_payment_answers_400_with_every_field() -> None:
    with pytest.raises(DomainError) as caught:
        validate_payment(_input(beneficiary_kind="pj", nature_code="99999", gross_amount="-1"), period_start=START, period_end=END)
    assert caught.value.status_code == 400
    assert {"nature_code", "gross_amount"} <= _locs(caught.value.errors)


def test_the_nature_table_has_no_rate_and_splits_by_beneficiary() -> None:
    table = reinf_natures()
    assert {item.code for item in table.items("pf")} == {"10002", "13002"}
    assert {item.code for item in table.items("pj")} == {"15014", "15015", "15043", "15044", "15045", "15046", "15099"}
    assert all(set(item.as_dict()) == {"code", "description", "beneficiary_kind"} for item in table.items())
    assert table.version


# Identificador, valores e nomes


def test_event_id_uses_the_root_padded_to_the_right_and_the_xsd_pattern() -> None:
    identifier = event_id(DECLARANT, GENERATED, 1)
    assert identifier == f"ID1{DECLARANT[:8]}000000{'20261111120000'}00001"
    assert len(identifier) == 36
    assert re.fullmatch(r"ID[0-9][0-9A-Z]{14}[0-9]{19}", identifier)
    assert event_id(ALPHANUMERIC, GENERATED, 12).startswith("ID112ABC345000000")
    with pytest.raises(ValueError):
        event_id(DECLARANT, GENERATED, 0)


def test_values_use_comma_and_two_places() -> None:
    assert format_value(Decimal("10000")) == "10000,00"
    assert format_value(Decimal("150.5")) == "150,50"
    assert format_value(Decimal("0.01")) == "0,01"
    assert format_value(Decimal("123456789012.34")) == "123456789012,34"


def test_file_name_carries_cnpj_and_competence() -> None:
    assert preview_file_name(DECLARANT, 2026, 3) == f"REINF-R4000-PREVIA-{DECLARANT}-202603.zip"


# Agrupamento


def test_one_event_per_beneficiary_with_payments_grouped_by_nature() -> None:
    payments = [
        _payment(payment_date="2026-10-20"),
        _payment(payment_date="2026-10-05", nature_code="15015"),
        _payment(payment_date="2026-10-02"),
        _payment(beneficiary_document=OTHER_SUPPLIER, nature_code="15043"),
        _person(),
        _person(payment_date="2026-10-25", nature_code="13002"),
    ]
    people, companies = group_payments(payments)
    assert [group.document for group in people] == [PERSON]
    assert [code for code, _ in people[0].natures] == ["13002"]
    assert len(people[0].natures[0][1]) == 2
    assert [group.document for group in companies] == sorted([SUPPLIER, OTHER_SUPPLIER])
    supplier = next(group for group in companies if group.document == SUPPLIER)
    assert [code for code, _ in supplier.natures] == ["15014", "15015"]
    assert [item.payment_date.day for item in supplier.natures[0][1]] == [2, 20]


# Eventos e XSD oficial


def _events(payments, responsible=Responsible("Maria Fictícia", cpf_digits("111444777"))):
    return build_events(cnpj=DECLARANT, year=2026, month=10, payments=payments, responsible=responsible, generated_at=GENERATED)


def test_official_xsds_are_kept_unmodified() -> None:
    for name, digest in OFFICIAL_SHA256.items():
        assert hashlib.sha256((XSD_DIR / name).read_bytes()).hexdigest() == digest, name


def test_generated_events_validate_against_the_official_xsd() -> None:
    events = _events([_payment(), _payment(beneficiary_document=OTHER_SUPPLIER, nature_code="15043", csrf_base=None, csrf_amount=None), _person()])
    assert [(event.kind, event.file_name) for event in events] == [
        ("R-4010", "R-4010-001.xml"),
        ("R-4020", "R-4020-001.xml"),
        ("R-4020", "R-4020-002.xml"),
        ("R-4099", "R-4099-001.xml"),
    ]
    assert [event.event_id[-5:] for event in events] == ["00001", "00002", "00003", "00004"]
    for event in events:
        assert xsd_errors(event.kind, event.xml) == [], event.file_name
        assert b"Signature" not in event.xml


def test_company_event_carries_comma_values_and_the_aggregated_csrf() -> None:
    events = _events([_payment()])
    root = etree.fromstring(events[0].xml)
    ns = {"r": EVENTS["R-4020"]["ns"]}
    assert root.find("r:evtRetPJ", ns).get("id") == events[0].event_id
    assert root.findtext("r:evtRetPJ/r:ideEvento/r:perApur", namespaces=ns) == "2026-10"
    assert root.findtext("r:evtRetPJ/r:ideEvento/r:tpAmb", namespaces=ns) == "2"
    assert root.findtext("r:evtRetPJ/r:ideContri/r:nrInsc", namespaces=ns) == DECLARANT[:8]
    assert root.findtext("r:evtRetPJ/r:ideEstab/r:nrInscEstab", namespaces=ns) == DECLARANT
    info = root.find("r:evtRetPJ/r:ideEstab/r:ideBenef/r:idePgto/r:infoPgto", ns)
    assert info.findtext("r:dtFG", namespaces=ns) == "2026-10-20"
    assert info.findtext("r:vlrBruto", namespaces=ns) == "10000,00"
    assert [(child.tag.split("}")[1], child.text) for child in info.find("r:retencoes", ns)] == [
        ("vlrBaseIR", "10000,00"),
        ("vlrIR", "150,00"),
        ("vlrBaseAgreg", "10000,00"),
        ("vlrAgreg", "465,00"),
    ]
    assert root.find("r:evtRetPJ/r:ideEstab/r:ideBenef/r:nmBenef", ns) is None


def test_closing_without_responsible_still_validates_in_the_xsd() -> None:
    events = _events([_person(ir_amount=None)], responsible=None)
    closing = events[-1]
    assert closing.kind == "R-4099"
    assert xsd_errors(closing.kind, closing.xml) == []
    assert b"ideRespInf" not in closing.xml
    assert b"<fechRet>0</fechRet>" in closing.xml


def test_no_payment_means_no_event() -> None:
    assert _events([]) == []


def test_an_xsd_failure_is_reported() -> None:
    events = _events([_payment()], responsible=Responsible("x" * 80, cpf_digits("111444777")))
    errors = xsd_errors("R-4099", events[-1].xml)
    assert errors and "nmResp" in errors[0]
    unsigned = etree.fromstring(events[0].xml)
    assert unsigned.find(f"{{{DSIG}}}Signature") is None


def test_an_xsd_failure_turns_into_a_blocker_issue() -> None:
    valid, issues = validate_events(_events([_payment()], responsible=Responsible("x" * 80, cpf_digits("111444777"))))
    assert valid is False
    assert [(issue.code, issue.severity, issue.event, issue.fix) for issue in issues] == [
        ("xsd_invalid", "blocker", "R-4099", "signatories")
    ]
    assert issues[0].message.startswith("R-4099-001.xml não valida no XSD oficial: linha ")
    assert validate_events(_events([_payment()])) == (True, [])
    assert validate_events([]) == (False, [])


def test_package_has_one_xml_per_event_and_the_readme() -> None:
    events = _events([_payment(), _person()])
    content = package(events, readme_text("2026-10", DECLARANT, events), GENERATED)
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        names = archive.namelist()
        readme = archive.read("LEIA-ME.txt").decode("utf-8")
        assert all(b"Signature" not in archive.read(name) for name in names if name.endswith(".xml"))
    assert names == ["LEIA-ME.txt", "R-4010-001.xml", "R-4020-001.xml", "R-4099-001.xml"]
    assert "NÃO ASSINAR NEM TRANSMITIR" in readme
    assert "ds:Signature" in readme
    assert package(events, readme_text("2026-10", DECLARANT, events), GENERATED) == content


# Pendências sobre o que está gravado


def _row(**overrides):
    base = {
        "beneficiary_kind": "pj",
        "beneficiary_document": SUPPLIER,
        "beneficiary_name": "Consultoria Fictícia Ltda.",
        "nature_code": "15014",
        "payment_date": date(2026, 10, 20),
        "gross_amount": Decimal("1000.00"),
        "ir_base": Decimal("1000.00"),
        "ir_amount": None,
        "csrf_base": None,
        "csrf_amount": None,
        "description": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_stored_payments_are_checked_again() -> None:
    period = SimpleNamespace(start_date=START, end_date=END)
    rows = [
        _row(),
        _row(nature_code="15999"),
        _row(payment_date=date(2026, 9, 30)),
        _row(beneficiary_document=DECLARANT),
    ]
    clean, issues = payment_issues(rows, period, DECLARANT, reinf_natures())
    codes = [issue.code for issue in issues]
    assert len(clean) == 2
    assert "nature_outside_table" in codes
    assert "payment_invalid" in codes
    assert "beneficiary_is_declarant" in codes
    assert "ir_not_withheld" in codes
    blockers = [issue for issue in issues if issue.severity == "blocker"]
    assert {issue.fix for issue in blockers} == {"withholding_payments"}
