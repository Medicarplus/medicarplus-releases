#!/usr/bin/env python3
"""Focused verification for MediCar Plus support email bug.

Checks that PREVIEW static HTML files no longer contain the old
info@medicarplus.es address and that mailer.py uses suport@ as Reply-To.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path


BASE = "https://project-helper-47.preview.emergentagent.com"
OLD = "info@medicarplus.es"
NEW = "suport@medicarplus.es"

URL_PATHS = [
    "/subscription-success.html",
    "/downloads/landing-medicarplus.html",
    "/terminos-uso.html",
    "/guia-client-installacio.html",
]

LOCAL_FILES = [
    Path("/app/frontend/public/subscription-success.html"),
    Path("/app/frontend/public/downloads/landing-medicarplus.html"),
    Path("/app/frontend/public/terminos-uso.html"),
    Path("/app/frontend/public/guia-client-installacio.html"),
]

MAILER = Path("/app/backend/services/mailer.py")


def fetch(url: str) -> tuple[int, str]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "bug-verification-support-email/1.0",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 - controlled QA URL
        raw = resp.read()
        return resp.status, raw.decode("utf-8", errors="replace")


def count(text: str, needle: str) -> int:
    return text.count(needle)


def main() -> int:
    results: dict[str, object] = {"preview": {}, "local_files": {}, "mailer": {}}
    failures: list[str] = []

    for path in URL_PATHS:
        url = BASE + path
        try:
            status, body = fetch(url)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{url}: fetch failed: {exc}")
            results["preview"][path] = {"fetch_error": str(exc)}  # type: ignore[index]
            continue

        old_count = count(body, OLD)
        new_count = count(body, NEW)
        has_error_block_new = True
        if path == "/subscription-success.html":
            idx = body.find("No hemos podido verificar tu pago automáticamente")
            snippet = body[idx : idx + 500] if idx >= 0 else ""
            has_error_block_new = NEW in snippet and OLD not in snippet
        ok = status == 200 and old_count == 0 and new_count > 0 and has_error_block_new
        if not ok:
            failures.append(
                f"{url}: status={status}, old={old_count}, new={new_count}, "
                f"error_block_new={has_error_block_new}"
            )
        results["preview"][path] = {  # type: ignore[index]
            "status": status,
            "old_count": old_count,
            "new_count": new_count,
            "subscription_error_block_uses_new": has_error_block_new if path == "/subscription-success.html" else None,
        }

    for file_path in LOCAL_FILES:
        text = file_path.read_text(encoding="utf-8", errors="replace")
        old_count = count(text, OLD)
        new_count = count(text, NEW)
        if old_count != 0 or new_count == 0:
            failures.append(f"{file_path}: old={old_count}, new={new_count}")
        results["local_files"][str(file_path)] = {"old_count": old_count, "new_count": new_count}  # type: ignore[index]

    mailer_text = MAILER.read_text(encoding="utf-8", errors="replace")
    has_reply_fn = bool(re.search(r"def\s+_reply_to\s*\(\s*\)", mailer_text))
    default_new = "REPLY_TO_EMAIL" in mailer_text and NEW in mailer_text
    reply_to_params = len(re.findall(r'"reply_to"\s*:\s*\[_reply_to\(\)\]', mailer_text))
    mailer_old_count = count(mailer_text, OLD)
    if not has_reply_fn or not default_new or reply_to_params < 2 or mailer_old_count != 0:
        failures.append(
            f"mailer.py: has_reply_fn={has_reply_fn}, default_new={default_new}, "
            f"reply_to_params={reply_to_params}, old={mailer_old_count}"
        )
    results["mailer"] = {
        "has_reply_to_function": has_reply_fn,
        "default_is_suport": default_new,
        "resend_reply_to_params_count": reply_to_params,
        "old_count": mailer_old_count,
    }

    print(json.dumps(results, indent=2, ensure_ascii=False))
    if failures:
        print("FAILURES:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("PASS: Preview and local files use suport@medicarplus.es and contain zero info@medicarplus.es.")
    return 0


if __name__ == "__main__":
    sys.exit(main())