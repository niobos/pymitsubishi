import pytest

from pymitsubishi.mitsubishi_api import MitsubishiAPI, KEY_SIZE


@pytest.mark.parametrize(
    'plain,iv,cipher',
    [
        ("A", b'\0'*KEY_SIZE, "AAAAAAAAAAAAAAAAAAAAAIT5vD/rsXTBfN0pB8TPkxc="),
        ("A", b'\x01'*KEY_SIZE, "AQEBAQEBAQEBAQEBAQEBAarATh0bybQe2zZhADpDvQQ="),  # Test that IV changes cipher
        ("B", b'\0'*KEY_SIZE, "AAAAAAAAAAAAAAAAAAAAAPmn52wIefATSMKaGbP0/bk="),  # Test that plain changes cipher
        # Test padding:
        ("A"*(KEY_SIZE-1), b'\0'*KEY_SIZE, "AAAAAAAAAAAAAAAAAAAAAMvpLQLHDQAG1qremOilhhQ="),
        ("A"*(KEY_SIZE+0), b'\0'*KEY_SIZE, "AAAAAAAAAAAAAAAAAAAAACzlU7obsl2kJ0Q7LuPErLogiP/E99wLWbwOvLS48OHt"),
        ("A"*(KEY_SIZE+1), b'\0'*KEY_SIZE, "AAAAAAAAAAAAAAAAAAAAACzlU7obsl2kJ0Q7LuPErLrOVkkQTm+1G0tfe1fsFb87"),
    ],
)
def test_encrypt(plain, iv, cipher):
    api = MitsubishiAPI("localhost")
    enc = api.encrypt_payload(plain, iv)
    assert enc == cipher

    dec = api.decrypt_payload(enc)
    assert dec == plain
