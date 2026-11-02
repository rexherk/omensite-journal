"""Discord sign-in. The journal still lives on this server."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

from app.auth import new_token
from app.paths import data_dir

STATE_COOKIE = "omensite_discord_state"
AUTHORIZE = "https://discord.com/oauth2/authorize"
TOKEN_URL = "https://discord.com/api/oauth2/token"
ME_URL = "https://discord.com/api/users/@me"


class DiscordNotConfigured(Exception):
    pass


class DiscordError(Exception):
    pass


def _file_values() -> dict[str, str]:
    path = data_dir() / "discord.env"
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
    client_id = os.environ.get("OMENSITE_DISCORD_CLIENT_ID", "").strip()
    secret = os.environ.get("OMENSITE_DISCORD_CLIENT_SECRET", "").strip()
    if client_id and secret:
        return client_id, secret
    stored = _file_values()
    return client_id or stored.get("OMENSITE_DISCORD_CLIENT_ID", ""), secret or stored.get(
        "OMENSITE_DISCORD_CLIENT_SECRET", ""
    )


def redirect_uri(request) -> str:
    return str(request.base_url).rstrip("/") + "/auth/discord/callback"


def authorize_url(request) -> tuple[str, str]:
    client_id, secret = credentials()
    if not client_id or not secret:
        raise DiscordNotConfigured(
            "Discord sign-in needs OMENSITE_DISCORD_CLIENT_ID and OMENSITE_DISCORD_CLIENT_SECRET. "
            "Put them in the environment, or in data/discord.env, and register the redirect "
            + redirect_uri(request)
            + " on the Discord application."
        )
    state = new_token()
    query = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri(request),
            "response_type": "code",
            "scope": "identify email",
            "state": state,
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
        raise DiscordError("Discord did not accept the sign-in.") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise DiscordError("Discord could not be reached.") from exc


def _get_json(url: str, token: str) -> dict:
    request = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise DiscordError("Discord did not return the account.") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise DiscordError("Discord could not be reached.") from exc


def fetch_profile(request, code: str) -> dict:
    client_id, secret = credentials()
    if not client_id or not secret:
        raise DiscordNotConfigured("Discord sign-in is not configured on this server.")
    if not code:
        raise DiscordError("Discord did not return a sign-in code.")
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
        raise DiscordError("Discord did not accept the sign-in.")
    profile = _get_json(ME_URL, access)
    if not profile.get("id"):
        raise DiscordError("Discord did not return the account.")
    return profile
