"""Payments proxy — mirrors admin-v2/src/store/api/paymentsApi.ts.

NOTE: the dashboard's payments slice uses a plain `fetchBaseQuery` (not the
authenticated `createBaseQuery`), so the upstream payments Lambda is called
UNAUTHENTICATED — no Bearer token. We mirror that with `auth=False` on every
call. `@require_marzi()` still guards the Frappe-side proxy entry point.
"""

import frappe

from marzi_bridge.client import MarziClient, request_params
from marzi_bridge.permissions import require_marzi


@frappe.whitelist()
@require_marzi()
def list_all_payments():
	return MarziClient().get(
		"/payment/all",
		service="payments",
		auth=False,
		params=request_params(),
	)


@frappe.whitelist()
@require_marzi()
def list_payments_by_mobile():
	return MarziClient().get(
		"/payment/payments",
		service="payments",
		auth=False,
		params=request_params(),
	)
