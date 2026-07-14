"""Speakers proxy (PILOT).

Thin pass-through to the backend `/speakers` routes (Backend-for-org API_DOC §5).
This module is the reference pattern for every other feature proxy:

- `@frappe.whitelist()` is the OUTERMOST decorator (framework entry point).
- `@require_marzi()` gates on the `Marzi Admin` role.
- The function body only maps args → `MarziClient` call and returns the JSON.
  No business logic lives here — the backend owns the contract.
- Path params come in as function args; query/body args are forwarded via
  `request_params()` (which reads both the query string and a JSON body).
"""

import frappe

from marzi_bridge.client import MarziClient, request_params
from marzi_bridge.permissions import require_marzi


@frappe.whitelist()
@require_marzi()
def list_speakers():
	return MarziClient().get("/speakers", params=request_params())


@frappe.whitelist()
@require_marzi()
def get_speaker(speaker_id: str):
	return MarziClient().get(f"/speakers/{speaker_id}")


@frappe.whitelist()
@require_marzi()
def create_speaker():
	return MarziClient().post("/speakers", json_body=request_params())


@frappe.whitelist()
@require_marzi()
def update_speaker(speaker_id: str):
	return MarziClient().patch(f"/speakers/{speaker_id}", json_body=request_params(exclude=["speaker_id"]))


@frappe.whitelist()
@require_marzi()
def delete_speaker(speaker_id: str):
	return MarziClient().delete(f"/speakers/{speaker_id}")
