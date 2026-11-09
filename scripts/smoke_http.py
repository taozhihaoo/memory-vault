"""HTTP smoke test for a running MemoryVault server or Docker container.

Checks the bundled dashboard, the JSON API, SPA routing, the favicon and the
local-only CORS policy. Used by the Docker job in CI.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request


def fetch(base: str, path: str, headers: dict[str, str] | None = None):
    request = urllib.request.Request(base + path, headers=headers or {})
    with urllib.request.urlopen(request, timeout=5) as response:
        return response.status, dict(response.headers), response.read().decode("utf-8", "replace")


def wait_until_healthy(base: str, timeout: float = 60.0) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            status, _, body = fetch(base, "/api/health")
            if status == 200 and json.loads(body).get("status") == "ok":
                return
        except Exception as exc:  # noqa: BLE001 - transient startup errors
            last_error = exc
        time.sleep(1)
    raise SystemExit(f"server never became healthy: {last_error}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    base = args.base.rstrip("/")

    wait_until_healthy(base)

    _, _, search = fetch(base, "/api/search?q=quantum")
    assert "total" in json.loads(search), "search endpoint returned no total"

    _, _, index = fetch(base, "/")
    assert 'id="root"' in index, "dashboard HTML was not served"

    status, _, _ = fetch(base, "/favicon.svg")
    assert status == 200, "favicon missing from the production bundle"

    try:
        fetch(base, "/api/definitely-missing")
    except urllib.error.HTTPError as exc:
        assert exc.code == 404, f"unknown API route returned {exc.code}, expected 404"
    else:
        raise AssertionError("unknown API route did not return 404")

    # Any website on the internet must not be able to read a local vault.
    _, evil_headers, _ = fetch(
        base, "/api/health", {"Origin": "https://evil.example"}
    )
    assert not any(k.lower() == "access-control-allow-origin" for k in evil_headers), \
        "API allows arbitrary cross-origin access"

    _, local_headers, _ = fetch(
        base, "/api/health", {"Origin": "http://localhost:5173"}
    )
    assert any(k.lower() == "access-control-allow-origin" for k in local_headers), \
        "local dev origin is blocked"

    print(f"HTTP smoke test passed for {base}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
