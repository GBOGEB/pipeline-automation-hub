"""Fail-closed, token-safe source-access evidence for the read-only live census.

HTTP 404 from the GitHub API can mean private/inaccessible, absent, or invalid
ref. None of those conditions establishes a zero-sized or healthy census.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


class SourceAccessError(RuntimeError):
    """A GitHub source read failed; never infer which underlying cause won."""

    def __init__(self, resource: str, http_status: int | None = None, reason: str = "HTTP"):
        components = resource.split("/")
        self.repository = components[3] if len(components) > 3 else "UNKNOWN"
        self.endpoint_class = components[4] if len(components) > 4 else "UNKNOWN"
        self.http_status = http_status
        self.reason_class = reason
        if http_status in (401, 403, 404):
            self.classification = "SOURCE_VISIBILITY_OR_IDENTITY_UNKNOWN"
        elif http_status == 429:
            self.classification = "SOURCE_RATE_LIMIT_UNKNOWN"
        else:
            self.classification = "SOURCE_TRANSPORT_OR_API_UNKNOWN"
        # Only whitelisted path components and status are in the exception; no URLs,
        # headers, response bodies, token values or raw exception details.
        super().__init__(f"{self.classification}: {self.repository} {self.endpoint_class} status={http_status}")

    def diagnostic(self) -> dict:
        return {
            "schema": "missioncontrol.n13.source_access_diagnostic.v1",
            "observed_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "repository": self.repository,
            "endpoint_class": self.endpoint_class,
            "http_status": self.http_status,
            "reason_class": self.reason_class,
            "classification": self.classification,
            "source_sha": None,
            "source_present": None,
            "source_access_authorized": None,
            "fresh_census_generated": False,
            "accepted_causal_root_closures": None,
            "merge_authorized": False,
            "crew_dispatch_authorized": False,
            "engineering_acceptance": False,
            "disposition": "HOLD_OWNER_SOURCE_ACCESS_OR_REF_VERIFICATION",
        }


def read_json(request: urllib.request.Request, resource: str, *, timeout: int = 12, opener=None):
    """GET with typed access diagnostics, never leaking request credentials."""
    try:
        with (opener or urllib.request.urlopen)(request, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as err:
        raise SourceAccessError(resource, err.code) from None
    except (urllib.error.URLError, TimeoutError, OSError) as err:
        raise SourceAccessError(resource, reason=type(err).__name__) from None


CROSS_REPO_TOKEN_ENV = "CROSS_REPO_READ_TOKEN"
DEFERRED_NO_TOKEN = "DEFERRED_NO_CROSS_REPO_READ_TOKEN"


def credential_deferral() -> dict:
    """Typed receipt for a census that was NOT attempted: no cross-repo credential.

    A repository-scoped GITHUB_TOKEN cannot read sibling private repositories, so
    every GET would 404. That is a known configuration absence, not a fresh
    source-visibility observation, so no request is made and nothing is credited.
    """
    return {
        "schema": "missioncontrol.n13.source_access_diagnostic.v1",
        "observed_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "repository": None,
        "endpoint_class": None,
        "http_status": None,
        "reason_class": "CREDENTIAL_NOT_CONFIGURED",
        "classification": "CROSS_REPO_CREDENTIAL_ABSENT",
        "credential_env": CROSS_REPO_TOKEN_ENV,
        "requests_attempted": 0,
        "source_sha": None,
        "source_present": None,
        "source_access_authorized": None,
        "fresh_census_generated": False,
        "accepted_causal_root_closures": None,
        "merge_authorized": False,
        "crew_dispatch_authorized": False,
        "engineering_acceptance": False,
        "disposition": DEFERRED_NO_TOKEN,
    }


def write_diagnostic(error: "SourceAccessError | dict", out_dir: Path) -> Path:
    """Durable diagnostic even when native refresh cannot emit a valid snapshot."""
    payload = error if isinstance(error, dict) else error.diagnostic()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "access_diagnostic.json"
    tmp = out / "access_diagnostic.json.tmp"
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)
    return path
