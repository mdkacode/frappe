"""Base controller for API-backed **Virtual DocTypes**.

Each concrete DocType is `is_virtual = 1`: it has no table. Its data lives in
Backend-for-org and is reached live through `MarziClient`, so the backend stays the
single source of truth (Phase-1 principle — no duplication, contracts unchanged).

This base implements the virtual-doctype contract once; a concrete controller only
declares the mapping:

    class MarziSpeaker(ApiDocument):
        DOCTYPE       = "Marzi Speaker"
        api_endpoint  = "/speakers"
        api_id_field  = "speaker_id"     # backend key that identifies a record
        api_service   = "v1"
        api_list_key  = "speakers"       # envelope key on the list response
        api_item_key  = "speaker"        # envelope key on a single-item response
        api_field_aliases = {"name": "speaker_name"}   # backend_key -> frappe field
        api_write_fields  = ("speaker_name", "age", ...)  # sent on create/update

Frappe validates that `get_list` / `get_count` / `get_stats` are *staticmethods*
(`frappe.model.virtual_doctype`). Static methods can't see the subclass, so each
concrete controller adds three one-line staticmethods that delegate to the
classmethod helpers here (`_api_list` / `_api_count`). Everything else is inherited.
"""

import json

import frappe
from frappe.model.document import Document

from marzi_bridge.client import MarziClient

_LAYOUT_FIELDTYPES = {"Section Break", "Column Break", "Tab Break", "HTML", "Button", "Fold"}
# Fieldtypes that can hold a serialized nested object/array for read-only display.
_JSON_FIELDTYPES = {"Code", "JSON", "Long Text"}


class ApiDocument(Document):
	# -- declarative config (override in subclasses) ---------------------------
	DOCTYPE: str = ""
	api_endpoint: str = ""
	api_id_field: str = "id"
	api_service: str = "v1"
	api_list_key: str | None = None
	api_item_key: str | None = None
	api_auth: bool = True
	api_field_aliases: dict = {}
	api_write_fields: tuple = ()
	# When the backend has no GET /<endpoint>/<id>, load a single record by pulling
	# the collection and matching on the id field instead.
	api_single_from_list: bool = False
	# A richer GET-by-id detail route when it differs from the list endpoint
	# (e.g. list = /admin/events, detail = /events/<id>). Falls back to api_endpoint.
	api_detail_endpoint: str | None = None
	# Sibling envelope keys to fold onto the item on a detail read. The blog detail
	# returns {"post": {...}, "tags": [...]}; merging "tags" lets a child table map it.
	api_merge_keys: tuple = ()
	# Relational collections shown as child-table grids on the Form. Each entry:
	#   frappe_table_field -> {
	#       "doctype":   child DocType name,
	#       "source":    "item" (array already on the detail object) OR a sub-route
	#                    template like "/groups/{id}/members" (a second GET),
	#       "item_key":  dotted key of the array on the item        (source == "item"),
	#       "list_key":  dotted key of the array in the sub-route response,
	#       "service":   upstream service for the sub-route          (default api_service),
	#       "aliases":   backend_key -> child fieldname,
	#   }
	api_child_tables: dict = {}

	# -- envelope helpers ------------------------------------------------------
	@staticmethod
	def _dig(data, path):
		"""Traverse a dotted envelope path, e.g. 'data.items'."""
		for part in path.split("."):
			if not isinstance(data, dict):
				return None
			data = data.get(part)
		return data

	@classmethod
	def _unwrap_list(cls, data):
		if cls.api_list_key:
			return cls._dig(data, cls.api_list_key) or []
		if isinstance(data, dict):
			for value in data.values():  # fall back to the first list in the envelope
				if isinstance(value, list):
					return value
			return []
		return data or []

	@classmethod
	def _unwrap_item(cls, data):
		if cls.api_item_key:
			return cls._dig(data, cls.api_item_key)
		if isinstance(data, dict):
			# Auto-strip common single-item envelopes: {"data": {...}} or {"speaker": {...}}.
			inner = data.get("data")
			if isinstance(inner, dict):
				return inner
			dict_values = [v for v in data.values() if isinstance(v, dict)]
			if len(dict_values) == 1 and len(data) <= 2:
				return dict_values[0]
		return data

	@staticmethod
	def _map_obj(doctype: str, obj: dict, aliases: dict, id_field: str | None = None) -> "frappe._dict":
		"""Backend object -> a Frappe row dict for `doctype` (only declared fields).

		Values destined for a Code/JSON/Long Text field are JSON-serialized when
		they are a dict/list, so nested objects/arrays display read-only instead of
		being dropped (or blowing up a scalar field).
		"""
		meta = frappe.get_meta(doctype)
		fieldtypes = {df.fieldname: df.fieldtype for df in meta.fields}
		row = frappe._dict()
		for key, value in (obj or {}).items():
			target = aliases.get(key, key)
			ftype = fieldtypes.get(target)
			if ftype is None:
				continue
			if ftype in _JSON_FIELDTYPES and isinstance(value, (dict, list)):
				value = json.dumps(value, indent=2, default=str, ensure_ascii=False)
			row[target] = value
		if id_field:
			row["name"] = (obj or {}).get(id_field)
		return row

	@classmethod
	def _to_row(cls, obj: dict) -> "frappe._dict":
		"""Backend object -> a Frappe row dict (mapped fieldnames + `name`)."""
		return cls._map_obj(cls.DOCTYPE, obj, cls.api_field_aliases, cls.api_id_field)

	def _to_body(self) -> dict:
		"""This doc -> a backend request body (reverse aliases, writable fields only)."""
		reverse = {v: k for k, v in self.api_field_aliases.items()}
		meta = frappe.get_meta(self.DOCTYPE)
		body = {}
		for df in meta.fields:
			if df.fieldtype in _LAYOUT_FIELDTYPES:
				continue
			if self.api_write_fields and df.fieldname not in self.api_write_fields:
				continue
			key = reverse.get(df.fieldname, df.fieldname)
			body[key] = self.get(df.fieldname)
		return body

	# -- classmethod helpers backing the (static) list/count ------------------
	@classmethod
	def _api_list(cls, filters=None, start=0, page_length=20, order_by=None, **kwargs):
		data = MarziClient().get(cls.api_endpoint, service=cls.api_service, auth=cls.api_auth)
		rows = [cls._to_row(obj) for obj in cls._unwrap_list(data)]
		# Backends here return whole collections; paginate locally to match the list view.
		try:
			start, page_length = int(start or 0), int(page_length or 0)
		except (TypeError, ValueError):
			start, page_length = 0, 0
		return rows[start : start + page_length] if page_length else rows[start:]

	@classmethod
	def _api_count(cls, filters=None, **kwargs) -> int:
		data = MarziClient().get(cls.api_endpoint, service=cls.api_service, auth=cls.api_auth)
		return len(cls._unwrap_list(data))

	# -- virtual doctype contract: instance methods ---------------------------
	def load_from_db(self):
		if self.api_single_from_list:
			obj = self._find_in_list(self.name)
		else:
			endpoint = self.api_detail_endpoint or self.api_endpoint
			data = MarziClient().get(
				f"{endpoint}/{self.name}", service=self.api_service, auth=self.api_auth
			)
			obj = self._unwrap_item(data)
			# Fold sibling envelope keys onto the item (e.g. blog detail {post, tags}).
			if isinstance(obj, dict):
				for mk in self.api_merge_keys:
					sibling = self._dig(data, mk) if isinstance(data, dict) else None
					if sibling is not None:
						obj = {**obj, mk: sibling}
		if not obj:
			raise frappe.DoesNotExistError
		row = self._to_row(obj)
		row["name"] = self.name
		# Child-table grids for relational collections. Each is best-effort: a failed
		# sub-route (permission/empty/absent) leaves an empty grid but still opens the Form.
		for fieldname, spec in (self.api_child_tables or {}).items():
			try:
				child_objs = self._fetch_child_rows(obj, spec)
				child_dt = spec["doctype"]
				child_aliases = spec.get("aliases", {})
				row[fieldname] = [self._map_obj(child_dt, o, child_aliases) for o in child_objs]
			except Exception:  # noqa: BLE001 — never let a sub-fetch break the detail Form
				frappe.log_error(
					title=f"Marzi Bridge: child table '{fieldname}' failed for {self.DOCTYPE} {self.name}"
				)
				row[fieldname] = []
		super(Document, self).__init__(row)

	def _fetch_child_rows(self, obj: dict, spec: dict) -> list:
		"""Resolve a child-table collection: either inline on `obj` or via a sub-route."""
		source = spec["source"]
		if source == "item":
			raw = self._dig(obj, spec["item_key"]) if spec.get("item_key") else None
			return raw if isinstance(raw, list) else []
		path = source.format(id=self.name)
		data = MarziClient().get(
			path, service=spec.get("service", self.api_service), auth=self.api_auth
		)
		if spec.get("list_key"):
			raw = self._dig(data, spec["list_key"])
			return raw if isinstance(raw, list) else []
		return self._unwrap_list(data)

	@classmethod
	def _find_in_list(cls, record_id):
		data = MarziClient().get(cls.api_endpoint, service=cls.api_service, auth=cls.api_auth)
		for obj in cls._unwrap_list(data):
			if str((obj or {}).get(cls.api_id_field)) == str(record_id):
				return obj
		return None

	def db_insert(self, *args, **kwargs):
		data = MarziClient().post(
			self.api_endpoint, service=self.api_service, auth=self.api_auth, json_body=self._to_body()
		)
		obj = self._unwrap_item(data) or {}
		new_id = obj.get(self.api_id_field)
		if new_id:
			self.name = new_id

	def db_update(self, *args, **kwargs):
		MarziClient().patch(
			f"{self.api_endpoint}/{self.name}",
			service=self.api_service,
			auth=self.api_auth,
			json_body=self._to_body(),
		)

	def delete(self, *args, **kwargs):
		MarziClient().delete(
			f"{self.api_endpoint}/{self.name}", service=self.api_service, auth=self.api_auth
		)
