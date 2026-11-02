"""Google sign-in. The journal still lives on this server."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

from app.auth import new_token
from app.paths import data_dir

STATE_COOKIE = "omensite_google_state"
AUTHORIZE = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
ME_URL = "https://www.googleapis.com/oauth2/v2/userinfo"


class GoogleNotConfigured(Exception):
    pass


class GoogleError(Exception):
    pass


def _file_values() -> dict[str, str]:
    path = data_dir() / "google.env"
    found: dict[str, str] = {}
    if not path.is_file():
        return found
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text or text.startswith("#") or "=" not in text:
            continue
        key, value = text.split("=", 1)
        found[key.strip()] = value.strip().strip('"').strip("'")
    return found


def credentials() -> tuple[str, str]:
    client_id = os.environ.get("OMENSITE_GOOGLE_CLIENT_ID", "").strip()
    secret = os.environ.get("OMENSITE_GOOGLE_CLIENT_SECRET", "").strip()
    if client_id and secret:
        return client_id, secret
    stored = _file_values()
    return client_id or stored.get("OMENSITE_GOOGLE_CLIENT_ID", ""), secret or stored.get(
        "OMENSITE_GOOGLE_CLIENT_SECRET", ""
    )


def redirect_uri(request) -> str:
    return str(request.base_url).rstrip("/") + "/auth/google/callback"


def authorize_url(request) -> tuple[str, str]:
    client_id, secret = credentials()
    if not client_id or not secret:
        raise GoogleNotConfigured(
            "Google sign-in needs OMENSITE_GOOGLE_CLIENT_ID and OMENSITE_GOOGLE_CLIENT_SECRET. "
            "Put them in the environment, or in data/google.env, and register the redirect "
            + redirect_uri(request)
            + " on the Google client."
        )
    state = new_token()
    query = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri(request),
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "online",
        }
    )
    return f"{AUTHORIZE}?{query}", state


def _post_form(url: str, fields: dict[str, str]) -> dict:
    body = urllib.parse.urlencode(fields).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise GoogleError("Google did not accept the sign-in.") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise GoogleError("Google could not be reached.") from exc


def _get_json(url: str, token: str) -> dict:
    request = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise GoogleError("Google did not return the account.") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise GoogleError("Google could not be reached.") from exc


def fetch_profile(request, code: str) -> dict:
    client_id, secret = credentials()
    if not client_id or not secret:
        raise GoogleNotConfigured("Google sign-in is not configured on this server.")
    if not code:
        raise GoogleError("Google did not return a sign-in code.")
    token = _post_form(
        TOKEN_URL,
        {
            "client_id": client_id,
            "client_secret": secret,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri(request),
        },
    )
    access = str(token.get("access_token") or "")
    if not access:
        raise GoogleError("Google did not accept the sign-in.")
    profile = _get_json(ME_URL, access)
    if not profile.get("id"):
        raise GoogleError("Google did not return the account.")
    return profile
