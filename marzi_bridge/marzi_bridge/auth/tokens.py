"""Per-user token manager for the backend (marzi) session.

Each Frappe admin has a `Marzi User Link` holding their encrypted access + refresh
tokens. `get_valid_token` returns a currently-valid access token, transparently
refreshing it shortly before expiry. Tokens are relayed, not minted here — Frappe
never needs the backend's JWT signing secret.
"""

import base64
import json
import time

import frappe
from frappe import _
from frappe.utils import add_to_date, get_datetime, now_datetime

from marzi_bridge.marzi_bridge.doctype.marzi_user_link.marzi_user_link import get_link

# Refresh when the access token is within this many seconds of expiring.
_REFRESH_SKEW_SECONDS = 300
# Backend default token TTL (~30 days) — used only if the JWT omits exp/iat.
_DEFAULT_TTL_SECONDS = 30 * 24 * 3600


class NotLinkedError(frappe.ValidationError):
	pass


def get_valid_token(user: str | None = None) -> str:
	"""Return a valid access token for `user`, refreshing if near expiry."""
	link = _require_link(user)
	if _needs_refresh(link):
		return _refresh(link)
	return link.get_password("access_token")


def force_refresh(user: str | None = None) -> str:
	"""Unconditionally refresh and return a new access token."""
	return _refresh(_require_link(user))


def store_tokens(link, access: str, refresh: str) -> None:
	"""Persist tokens (encrypted) and derive the local expiry from the JWT."""
	link.access_token = access
	link.refresh_token = refresh
	link.access_expires_at = _expiry_from_jwt(access)
	link.save(ignore_permissions=True)


def jwt_claims(token: str) -> dict:
	"""Decode a JWT payload WITHOUT verifying the signature.

	Safe here: we only ever read tokens the backend just issued to us over TLS,
	to extract `role`/`exp`. We never trust these claims for authorization of
	third-party tokens.
	"""
	try:
		payload = token.split(".")[1]
		payload += "=" * (-len(payload) % 4)
		return json.loads(base64.urlsafe_b64decode(payload))
	except Exception:
		return {}


# -- internals -----------------------------------------------------------------


def _require_link(user: str | None):
	link = get_link(user or frappe.session.user)
	if not link:
		frappe.throw(
			_("Your Frappe account is not linked to a backend account. Link your phone first."),
			exc=NotLinkedError,
		)
	return link


def _needs_refresh(link) -> bool:
	if not link.access_expires_at:
		return False
	threshold = add_to_date(now_datetime(), seconds=_REFRESH_SKEW_SECONDS)
	return get_datetime(link.access_expires_at) <= threshold


def _refresh(link) -> str:
	from marzi_bridge.client import parse_response, raw_request

	refresh_token = link.get_password("refresh_token")
	if not refresh_token:
		_clear(link)
		frappe.throw(_("Your backend session has no refresh token. Re-link your phone."), exc=NotLinkedError)

	response = raw_request("POST", "/auth/refresh", version="v1", json_body={"refresh": refresh_token})
	if response.status_code != 200:
		_clear(link)
		frappe.throw(_("Your backend session has expired. Re-link your phone."), exc=NotLinkedError)

	data = (parse_response(response) or {}).get("data") or {}
	access = data.get("access")
	if not access:
		_clear(link)
		frappe.throw(_("Backend refresh did not return a token. Re-link your phone."), exc=NotLinkedError)

	store_tokens(link, access, data.get("refresh") or refresh_token)
	return access


def _expiry_from_jwt(access: str):
	claims = jwt_claims(access)
	exp, iat = claims.get("exp"), claims.get("iat")
	# Compute TTL relative to our own clock to avoid UTC/local timezone drift.
	if exp and iat:
		ttl = exp - iat
	elif exp:
		ttl = exp - int(time.time())
	else:
		ttl = _DEFAULT_TTL_SECONDS
	return add_to_date(now_datetime(), seconds=max(ttl, 0))


def _clear(link) -> None:
	link.access_token = None
	link.refresh_token = None
	link.access_expires_at = None
	link.save(ignore_permissions=True)
