import hashlib
import secrets


def _checksum(body: str) -> str:
    digest = hashlib.blake2b(body.encode(), digest_size=2).digest()
    value = int.from_bytes(digest) % 1296
    chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    result = []
    for _ in range(2):
        result.append(chars[value % 36])
        value //= 36
    return "".join(result)


def generate_agent_number(region: str = "GLOBAL") -> str:
    random_part = secrets.token_hex(5).upper()
    body = f"AN-{region}-{random_part}"
    suffix = _checksum(body)
    return f"{body}-{suffix}"