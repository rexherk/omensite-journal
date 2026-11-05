import io
import json
import unittest
import urllib.error
import urllib.parse
from types import SimpleNamespace
from unittest.mock import patch

from app import discord_auth


class DiscordAuthTests(unittest.TestCase):
    def test_code_exchange_identifies_client_and_keeps_credentials_in_body(self):
        profile = {"id": "123456789012345678", "username": "trader"}
        request = SimpleNamespace(base_url="https://journal.omensite.com/")
        replies = [io.BytesIO(json.dumps({"access_token": "test-access"}).encode()),
                   io.BytesIO(json.dumps(profile).encode())]
        with patch.object(discord_auth, "credentials", return_value=("test-client", "test-secret")), \
                patch.object(discord_auth.urllib.request, "urlopen", side_effect=replies) as send:
            self.assertEqual(discord_auth.fetch_profile(request, "test-code"), profile)

        exchange = send.call_args_list[0].args[0]
        self.assertEqual(exchange.full_url, discord_auth.TOKEN_URL)
        self.assertEqual(exchange.get_header("User-agent"), discord_auth.USER_AGENT)
        self.assertEqual(exchange.get_header("Content-type"), "application/x-www-form-urlencoded")
        self.assertEqual(urllib.parse.parse_qs(exchange.data.decode()), {
            "client_id": ["test-client"], "client_secret": ["test-secret"],
            "grant_type": ["authorization_code"], "code": ["test-code"],
            "redirect_uri": ["https://journal.omensite.com/auth/discord/callback"],
        })
        self.assertNotIn("test-secret", exchange.full_url)
        profile_request = send.call_args_list[1].args[0]
        self.assertEqual(profile_request.full_url, "https://discord.com/api/v10/users/@me")
        self.assertEqual(profile_request.get_header("User-agent"), discord_auth.USER_AGENT)
        self.assertEqual(profile_request.get_header("Authorization"), "Bearer test-access")

    def test_token_rejection_does_not_expose_credentials(self):
        failure = urllib.error.HTTPError(discord_auth.TOKEN_URL, 401, "Unauthorized", {},
                                         io.BytesIO(b'{"error":"invalid_client"}'))
        with patch.object(discord_auth, "credentials", return_value=("test-client", "test-secret")), \
                patch.object(discord_auth.urllib.request, "urlopen", side_effect=failure):
            with self.assertRaises(discord_auth.DiscordError) as caught:
                discord_auth.fetch_profile(SimpleNamespace(base_url="https://journal.omensite.com/"), "test-code")
        self.assertEqual(str(caught.exception), "Discord did not accept the sign-in.")
        self.assertNotIn("test-secret", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
