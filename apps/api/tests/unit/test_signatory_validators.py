from contabil.seed.cpf import cpf_digits
from contabil.signatories.validators import crc_label, masked_cpf, normalize_crc_number, valid_cpf, valid_crc_number


def test_cpf_check_digits() -> None:
    assert valid_cpf("529.982.247-25")
    assert valid_cpf("52998224725")
    assert not valid_cpf("529.982.247-24")
    assert not valid_cpf("111.111.111-11")
    assert not valid_cpf("123")


def test_cpf_mask_hides_edges() -> None:
    assert masked_cpf("52998224725") == "***.982.247-**"


def test_crc_number_format() -> None:
    assert valid_crc_number("012345/O-8")
    assert valid_crc_number(" 12345/o ")
    assert valid_crc_number("12345")
    assert not valid_crc_number("CRC-PE 12345")
    assert not valid_crc_number("12345/X")
    assert normalize_crc_number(" 12345/o-8 ") == "12345/O-8"


def test_crc_label() -> None:
    assert crc_label("PE", "012345/O-8") == "CRC-PE 012345/O-8"


def test_sample_cpf_generator_produces_valid_check_digits() -> None:
    assert cpf_digits("529982247") == "52998224725"
    for base in ("900000001", "900000002", "910000003"):
        assert valid_cpf(cpf_digits(base))
