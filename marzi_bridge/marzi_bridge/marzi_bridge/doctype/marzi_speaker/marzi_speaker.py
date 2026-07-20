"""Marzi Speaker — virtual DocType backed by the backend `/speakers` API.

All data lives in Backend-for-org; this controller maps Frappe's list/form actions
onto `MarziClient` calls. See `marzi_bridge.api_document.ApiDocument` for the
contract. Note: the backend's `name` field (the person's name) is aliased to
`speaker_name` because Frappe reserves `name` as the primary key.
"""

from marzi_bridge.api_document import ApiDocument


class MarziSpeaker(ApiDocument):
	DOCTYPE = "Marzi Speaker"
	api_endpoint = "/speakers"
	api_id_field = "speaker_id"
	api_service = "v1"
	api_list_key = "speakers"
	api_item_key = "speaker"
	api_field_aliases = {"name": "speaker_name"}
	api_write_fields = (
		"speaker_name",
		"age",
		"location",
		"about",
		"photo_url",
		"instagram",
		"twitter",
		"linkedin",
		"youtube",
		"website",
		"is_active",
	)

	# Frappe requires these three as staticmethods; delegate to the base helpers.
	@staticmethod
	def get_list(**kwargs):
		return MarziSpeaker._api_list(**kwargs)

	@staticmethod
	def get_count(**kwargs):
		return MarziSpeaker._api_count(**kwargs)

	@staticmethod
	def get_stats(**kwargs):
		return {}
