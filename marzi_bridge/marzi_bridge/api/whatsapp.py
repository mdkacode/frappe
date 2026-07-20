"""WhatsApp proxy — mirrors admin-v2/src/store/api/whatsappApi.ts.

NOTE: the dashboard's whatsapp slice uses a plain `fetchBaseQuery` (not the
authenticated `createBaseQuery`), so the upstream whatsapp Lambda is called
UNAUTHENTICATED — no Bearer token. We mirror that with `auth=False` on every
call. `@require_marzi()` still guards the Frappe-side proxy entry point.
"""

import frappe

from marzi_bridge.client import MarziClient, request_params
from marzi_bridge.permissions import require_marzi


@frappe.whitelist()
@require_marzi()
def list_conversations():
	return MarziClient().get(
		"/dashboard/conversations",
		service="whatsapp",
		auth=False,
		params=request_params(),
	)


@frappe.whitelist()
@require_marzi()
def get_messages():
	return MarziClient().get(
		"/dashboard/messages",
		service="whatsapp",
		auth=False,
		params=request_params(),
	)


@frappe.whitelist()
@require_marzi()
def send_message():
	return MarziClient().post(
		"/dashboard/messages/send",
		service="whatsapp",
		auth=False,
		json_body={**request_params(), "autoReply": False},
	)
