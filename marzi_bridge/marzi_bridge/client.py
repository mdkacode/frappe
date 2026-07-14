"""MarziClient — the single choke point for all outbound calls to the backend.

Every feature proxy goes through here. Responsibilities:
- build the URL from `Marzi Bridge Settings` (per-call `/v1` vs `/v3`)
- attach the caller's Bearer token (fetched/refreshed by `auth.tokens`)
- retry exactly once on a `401` after forcing a token refresh
- normalize backend error envelopes into a Frappe error (never logging tokens)

We use `frappe.utils.get_request_session()` directly (the same session helper that
`frappe.integrations.utils.make_request` uses) so we keep full control over status
codes for the 401-retry, instead of `make_request`'s `raise_for_status()` which also
logs every non-2xx to the Error Log.
"""

import frappe
from frappe import _
from frappe.utils import get_request_session

from marzi_bridge.marzi_bridge.doctype.marzi_bridge_settings.marzi_bridge_settings import (
	get_settings,
)


class MarziAPIError(frappe.ValidationError):
	pass


def _base_url(version: str) -> str:
	settings = get_settings()
	url = settings.v1_base_url if version == "v1" else settings.v3_base_url
	if not url:
		frappe.throw(_("Marzi Bridge Settings: {0} base URL is not configured.").format(version))
	return url


def _build_url(path: str, version: str) -> str:
	return f"{_base_url(version)}/{path.lstrip('/')}"


def raw_request(
	method: str,
	path: str,
	*,
	version: str = "v1",
	headers: dict | None = None,
	params: dict | None = None,
	json_body: dict | None = None,
	token: str | None = None,
):
	"""Low-level backend call. Unauthenticated unless `token` is supplied.

	Returns the raw `requests.Response` so callers can inspect the status code.
	"""
	settings = get_settings()
	headers = dict(headers or {})
	headers.setdefault("Accept", "application/json")
	if token:
		headers["Authorization"] = f"Bearer {token}"

	session = get_request_session()
	return session.request(
		method.upper(),
		_build_url(path, version),
		headers=headers,
		params=params or None,
		json=json_body,
		timeout=settings.request_timeout or 30,
		verify=bool(settings.verify_tls),
	)


def parse_response(response):
	"""Parse a JSON response body; fall back to text; None on empty."""
	content_type = response.headers.get("content-type", "")
	if "json" in content_type:
		try:
			return response.json()
		except ValueError:
			return None
	return response.text or None


def parse_body(data):
	"""Coerce an incoming body (JSON string or dict) into a dict for forwarding."""
	if data is None or data == "":
		return None
	if isinstance(data, str):
		return frappe.parse_json(data)
	return data


def request_params(exclude=None) -> dict:
	"""Forwardable request args: everything in form_dict except framework/path keys.

	Frappe merges a JSON request body into `form_dict`, so this captures both query
	params (GET) and body fields (POST/PUT/PATCH) uniformly for a pass-through proxy.
	"""
	skip = {"cmd"} | set(exclude or ())
	return {k: v for k, v in frappe.local.form_dict.items() if k not in skip}


class MarziClient:
	"""Authenticated client bound to a Frappe user (default: current session user)."""

	def __init__(self, user: str | None = None):
		self.user = user or frappe.session.user

	def request(self, method: str, path: str, *, version="v1", params=None, json_body=None):
		# Imported lazily to avoid a circular import (tokens -> client.raw_request).
		from marzi_bridge.auth.tokens import force_refresh, get_valid_token

		token = get_valid_token(self.user)
		response = raw_request(
			method, path, version=version, params=params, json_body=json_body, token=token
		)
		if response.status_code == 401:
			# Token rejected despite our local expiry check — refresh once and retry.
			token = force_refresh(self.user)
			response = raw_request(
				method, path, version=version, params=params, json_body=json_body, token=token
			)
		return self._handle(response, method, path)

	def _handle(self, response, method: str, path: str):
		if 200 <= response.status_code < 300:
			return parse_response(response)

		body = parse_response(response)
		message = None
		if isinstance(body, dict):
			message = body.get("message") or body.get("error") or body.get("detail")

		# Log status + body only — never the token or Authorization header.
		frappe.log_error(
			title=f"MarziClient {response.status_code} {method} {path}",
			message=frappe.as_json({"status": response.status_code, "body": body}),
		)
		frappe.throw(
			_("Backend request failed ({0}): {1}").format(
				response.status_code, message or "Unknown error"
			),
			exc=MarziAPIError,
		)

	def get(self, path, **kw):
		return self.request("GET", path, **kw)

	def post(self, path, **kw):
		return self.request("POST", path, **kw)

	def put(self, path, **kw):
		return self.request("PUT", path, **kw)

	def patch(self, path, **kw):
		return self.request("PATCH", path, **kw)

	def delete(self, path, **kw):
		return self.request("DELETE", path, **kw)
