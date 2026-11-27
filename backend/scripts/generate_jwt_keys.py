"""Write a new RS256 sign-in key pair into an env file.

    python scripts/generate_jwt_keys.py            # backend/.env
    python scripts/generate_jwt_keys.py path/.env

Replaces `LPG_JWT_PRIVATE_KEY` / `LPG_JWT_PUBLIC_KEY` (or appends them) and
leaves every other setting as it was. Only the public key's fingerprint is
printed. Access tokens signed with the old pair stop verifying.

For a server created by `infrastructure/deploy/generate-env.sh`, edit only
these two lines of its `.env`; never delete that file to regenerate it.
"""

from __future__ import annotations

import base64
import hashlib
import io
import re
import sys
from pathlib import Path

from dotenv import dotenv_values

from lpg.config.settings import generate_rs256_keypair

_NAMES = ("LPG_JWT_PRIVATE_KEY", "LPG_JWT_PUBLIC_KEY")


def _assignment(name: str) -> re.Pattern[str]:
    # A quoted value may span several lines; an unquoted one ends at the newline.
    return re.compile(
        rf"^[ \t]*{name}[ \t]*=[ \t]*(?:\"(?:[^\"\\]|\\.)*\"|'[^']*'|[^\r\n]*)[^\r\n]*",
        re.MULTILINE,
    )


def fingerprint(public_pem: str) -> str:
    """SHA-256 of the public key's DER bytes. Safe to share."""
    body = "".join(
        line.strip()
        for line in public_pem.replace("\\n", "\n").splitlines()
        if line.strip() and "-----" not in line
    )
    return hashlib.sha256(base64.b64decode(body)).hexdigest()


def replace_keys(text: str, private_pem: str, public_pem: str) -> str:
    """`text` with the two key settings set to the given PEMs."""
    newline = "\r\n" if "\r\n" in text else "\n"
    for name, pem in zip(_NAMES, (private_pem, public_pem), strict=True):
        escaped = pem.strip().replace("\r\n", "\n").replace("\n", "\\n") + "\\n"
        line = f"{name}='{escaped}'"
        pattern = _assignment(name)
        if pattern.search(text):
            # A function, so the backslashes are not read as group references.
            text = pattern.sub(lambda _, line=line: line, text, count=1)
        else:
            if text and not text.endswith("\n"):
                text += newline
            text += line + newline
    return text


def _other_settings(text: str) -> dict[str, str | None]:
    values = dotenv_values(stream=io.StringIO(text))
    return {key: value for key, value in values.items() if key not in _NAMES}


def write_new_keys(path: Path) -> str:
    """Rewrite `path` with a new pair and return its public fingerprint."""
    original = path.read_bytes().decode("utf-8")
    private_pem, public_pem = generate_rs256_keypair()
    updated = replace_keys(original, private_pem, public_pem)
    if _other_settings(updated) != _other_settings(original):
        msg = f"Refusing to write {path}: other settings would change."
        raise RuntimeError(msg)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(updated.encode("utf-8"))
    temporary.replace(path)
    return fingerprint(public_pem)


def main(argv: list[str]) -> int:
    path = Path(argv[0]) if argv else Path(__file__).resolve().parents[1] / ".env"
    if not path.is_file():
        print(f"{path} does not exist. Copy an .env example file to it first.")
        return 1
    new_fingerprint = write_new_keys(path)
    print(f"New key pair written to {path}")
    print(f"Public key fingerprint: {new_fingerprint}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
