"""Install the pinned Cloudflare Windows x64 release in this user's demo tools directory."""
import hashlib
import os
from pathlib import Path
import tempfile
import urllib.request

VERSION = "2026.11.1"
SHA256 = "341deda3db5ec498a0482254d6c38c0b7cf01a30c37bb5dd95d2216d08955e35"
HOME = Path(os.environ["LOCALAPPDATA"]) / "NiftyKPPrivateDemo"
BINARY = HOME / "tools" / f"cloudflared-{VERSION}.exe"
URL = f"https://github.com/cloudflare/cloudflared/releases/download/{VERSION}/cloudflared-windows-amd64.exe"

def verified_binary():
    if not BINARY.is_file() or hashlib.sha256(BINARY.read_bytes()).hexdigest() != SHA256:
        raise RuntimeError("Pinned cloudflared binary missing or checksum mismatch. Run private_demo/install_connector.py to repair.")
    return BINARY

def install():
    BINARY.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=BINARY.parent, delete=False) as file:
        tmp = Path(file.name)
    try:
        with urllib.request.urlopen(URL, timeout=90) as response, tmp.open("wb") as output:
            import shutil
            shutil.copyfileobj(response, output)
        if hashlib.sha256(tmp.read_bytes()).hexdigest() != SHA256:
            raise ValueError("Cloudflare release checksum mismatch")
        tmp.replace(BINARY)
    finally:
        tmp.unlink(missing_ok=True)

if __name__ == "__main__":
    install()
    print(verified_binary())

