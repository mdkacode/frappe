"""MarziClient — the single choke point for all outbound calls to the backend.

Every feature proxy goes through here. Responsibilities:
- build the URL from `Marzi Bridge Settings`, selecting the right upstream
  *service* per call (the dashboard talks to several: the unified gateway `v1`
  and `v3`, plus separate publishing / blog / tracking / whatsapp / payments hosts)
- attach the caller's Bearer token (fetched/refreshed by `auth.tokens`), except
  for services the dashboard itself calls unauthenticated (whatsapp, payments)
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


# Maps a logical service name (what a proxy module asks for) to the settings field
# holding its base URL. Mirrors the dashboard's per-slice base URLs — see
# admin-v2/src/store/api/*.ts and .env.example.
_SERVICE_FIELDS = {
	"v1": "v1_base_url",
	"v3": "v3_base_url",
	"publishing": "publishing_base_url",
	"blog": "blog_base_url",
	"tracking": "tracking_base_url",
	"whatsapp": "whatsapp_base_url",
	"payments": "payments_base_url",
}


def _resolve_service(service: str | None, version: str | None) -> str:
	# `version` is the legacy kwarg (v1/v3); `service` is the general one. Either works.
	return service or version or "v1"


def _base_url(service: str) -> str:
	field = _SERVICE_FIELDS.get(service)
	if not field:
		frappe.throw(_("Unknown backend service: {0}").format(service))
	url = get_settings().get(field)
	if not url:
		frappe.throw(_("Marzi Bridge Settings: {0} base URL is not configured.").format(service))
	return url


def _build_url(path: str, service: str) -> str:
	return f"{_base_url(service)}/{path.lstrip('/')}"


def raw_request(
	method: str,
	path: str,
	*,
	service: str | None = None,
	version: str | None = None,
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
		_build_url(path, _resolve_service(service, version)),
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

	def request(
		self, method: str, path: str, *, service=None, version=None, params=None, json_body=None, auth=True
	):
		svc = _resolve_service(service, version)

		# Some upstreams (whatsapp, payments) are called by the dashboard without a
		# Bearer token — mirror that. No token means no 401-refresh dance either.
		if not auth:
			response = raw_request(method, path, service=svc, params=params, json_body=json_body)
			return self._handle(response, method, path)

		# Imported lazily to avoid a circular import (tokens -> client.raw_request).
		from marzi_bridge.auth.tokens import force_refresh, get_valid_token

		token = get_valid_token(self.user)
		response = raw_request(
			method, path, service=svc, params=params, json_body=json_body, token=token
		)
		if response.status_code == 401:
			# Token rejected despite our local expiry check — refresh once and retry.
			token = force_refresh(self.user)
			response = raw_request(
				method, path, service=svc, params=params, json_body=json_body, token=token
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
