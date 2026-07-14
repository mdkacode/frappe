import frappe
from frappe.model.document import Document


class MarziBridgeSettings(Document):
	def validate(self):
		for field in ("v1_base_url", "v3_base_url"):
			value = self.get(field)
			if value:
				self.set(field, value.rstrip("/"))
		if self.request_timeout and self.request_timeout <= 0:
			frappe.throw("Request Timeout must be a positive number of seconds.")


def get_settings() -> "MarziBridgeSettings":
	"""Cached accessor for the singleton settings document."""
	return frappe.get_cached_doc("Marzi Bridge Settings")
