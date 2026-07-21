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
import re

import frappe
from frappe import _
from frappe.model.document import Document

from marzi_bridge.client import MarziClient, MarziAPIError

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
	# ---- write config (create / update / delete) ----------------------------
	# Top-level frappe fieldnames sent as body keys on write. Empty => read-only.
	api_write_fields: tuple = ()
	# Write base path when it differs from the read endpoint (Event list is
	# /admin/events but writes go to /events; Escalation reads .../pending). Falls
	# back to api_endpoint.
	api_write_endpoint: str | None = None
	# Id used in the write path/naming when it differs from api_id_field (e.g. a
	# publishing Campaign reads by one key but writes by `id`). Falls back to api_id_field.
	api_write_id_field: str | None = None
	# HTTP method for update: "PATCH" (default) or "PUT" (Event, Info Item).
	api_update_method: str = "PATCH"
	# Capability gates (surfaced as DocType perms too). Escalation is update-only.
	api_can_create: bool = True
	api_can_delete: bool = True
	# frappe field -> backend WRITE key, when write keys differ from the (reversed)
	# read aliases. Testimony writes name/quote/image; reads author_name/content/author_pic_url.
	api_write_aliases: dict = {}
	# Structured nested objects, assembled on write from flat frappe fields AND
	# flattened back onto them on a detail read (symmetric). backend_key -> {sub_key:
	# frappe_field}. e.g. {"defaultUtm": {"source": "utm_source", "medium": "utm_medium"}}.
	api_nested_fields: dict = {}
	# Nested objects flattened onto flat frappe fields on READ ONLY (the write body is
	# flat/asymmetric — e.g. a Page reads SEO under meta{} but writes flat metaTitle).
	api_read_nested: dict = {}
	# Object-arrays assembled on write from a child-table grid. backend_key -> {
	#   "field": frappe table fieldname, "map": {backend_sub_key: child_fieldname}}.
	api_write_child_tables: dict = {}
	# frappe Data fields whose comma string becomes a JSON array on write.
	api_write_array_fields: tuple = ()
	# Fields to send even when empty (rare — clearing a value on PATCH).
	api_write_always: tuple = ()
	# When the backend has no GET /<endpoint>/<id>, load a single record by pulling
	# the collection and matching on the id field instead.
	api_single_from_list: bool = False
	# A richer GET-by-id detail route when it differs from the list endpoint
	# (e.g. list = /admin/events, detail = /events/<id>). Falls back to api_endpoint.
	api_detail_endpoint: str | None = None
	# Extra query params sent on every list fetch (e.g. {"limit": 50}).
	api_list_params: dict = {}
	# Cursor pagination: when the list envelope carries a cursor (e.g. "nextCursor"),
	# _fetch_collection walks pages (passing it back as api_cursor_param) until the
	# rows needed are gathered, the cursor runs out, or api_max_pages is hit.
	api_cursor_key: str | None = None
	api_cursor_param: str = "cursor"
	api_max_pages: int = 10
	# Some detail endpoints return a SUBSET of the list row (e.g. GET /users/<id> is a
	# public-profile shape without phone/email/role). Merge the list row underneath the
	# detail object so the Form shows both.
	api_detail_merge_list: bool = False
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

	@staticmethod
	def _is_empty(value) -> bool:
		return value is None or value == "" or value == []

	def _to_body(self) -> dict:
		"""This doc -> a backend write body.

		Driven by `api_write_fields` (top-level scalars) plus `api_nested_fields`
		(assembled sub-objects) and `api_write_child_tables` (assembled object-arrays).
		Empty values are omitted so a PATCH never clobbers and a create sends no nulls
		(required-on-create is enforced by Frappe `reqd`). Server-computed fields simply
		aren't listed in `api_write_fields`, so they can never leak (e.g. final_amount).
		"""
		meta = frappe.get_meta(self.DOCTYPE)
		fieldtypes = {df.fieldname: df.fieldtype for df in meta.fields}
		# read aliases are backend->frappe; reverse for writing, then let write aliases win.
		reverse = {v: k for k, v in self.api_field_aliases.items()}
		reverse.update(self.api_write_aliases)

		body = {}
		for fieldname in self.api_write_fields:
			ftype = fieldtypes.get(fieldname)
			if ftype in _LAYOUT_FIELDTYPES:
				continue
			value = self.get(fieldname)
			if self._is_empty(value) and fieldname not in self.api_write_always:
				continue
			if ftype in _JSON_FIELDTYPES and isinstance(value, str) and value.strip():
				try:
					value = json.loads(value)
				except (ValueError, TypeError):
					frappe.throw(_("{0}: not valid JSON").format(fieldname), exc=MarziAPIError)
			elif fieldname in self.api_write_array_fields and isinstance(value, str):
				value = [v.strip() for v in value.split(",") if v.strip()]
			elif ftype == "Check":
				value = bool(value)
			body[reverse.get(fieldname, fieldname)] = value

		for backend_key, subspec in (self.api_nested_fields or {}).items():
			nested = self._nested_value(subspec)
			if nested:
				body[backend_key] = nested

		for backend_key, cspec in (self.api_write_child_tables or {}).items():
			rows = self._child_array(cspec)
			if rows:
				# "wrap" nests the array under a sub-key: config -> {"sections": [...]}.
				body[backend_key] = {cspec["wrap"]: rows} if cspec.get("wrap") else rows

		return body

	def _nested_value(self, subspec: dict) -> dict:
		"""Assemble a nested object from flat frappe fields; drop empty leaves."""
		out = {}
		for sub_key, ref in subspec.items():
			value = self._nested_value(ref) if isinstance(ref, dict) else self.get(ref)
			if not self._is_empty(value):
				out[sub_key] = value
		return out

	def _child_array(self, cspec: dict) -> list:
		"""Assemble an object-array from a child-table grid's rows."""
		child_dt = frappe.get_meta(self.DOCTYPE).get_field(cspec["field"]).options
		child_ft = {df.fieldname: df.fieldtype for df in frappe.get_meta(child_dt).fields}
		rows = []
		for row in (self.get(cspec["field"]) or []):
			obj = {}
			for backend_sub, child_field in cspec["map"].items():
				value = row.get(child_field)
				if child_ft.get(child_field) == "Check":
					obj[backend_sub] = bool(value)
				elif not self._is_empty(value):
					obj[backend_sub] = value
			if obj:
				rows.append(obj)
		return rows

	# -- classmethod helpers backing the (static) list/count ------------------
	@classmethod
	def _fetch_collection(cls, need: int | None = None) -> list:
		"""Fetch the backend collection; walk cursor pages when declared.

		`need` stops the walk once that many rows are gathered (list-view paging);
		None walks to the end (bounded by api_max_pages).
		"""
		client = MarziClient()
		rows, cursor, pages = [], None, 0
		while True:
			params = dict(cls.api_list_params or {})
			if cursor:
				params[cls.api_cursor_param] = cursor
			data = client.get(
				cls.api_endpoint,
				service=cls.api_service,
				auth=cls.api_auth,
				params=params or None,
			)
			batch = cls._unwrap_list(data)
			rows.extend(batch)
			pages += 1
			cursor = cls._dig(data, cls.api_cursor_key) if cls.api_cursor_key else None
			if (
				not cursor
				or not batch
				or pages >= cls.api_max_pages
				or (need is not None and len(rows) >= need)
			):
				return rows

	@classmethod
	def _field_set(cls) -> set:
		"""Frappe fieldnames on this DocType (+ `name`) — what we can filter/sort on."""
		return {df.fieldname for df in frappe.get_meta(cls.DOCTYPE).fields} | {"name"}

	@classmethod
	def _normalize_filters(cls, filters) -> list:
		"""Coerce whatever the list view sends into [(fieldname, operator, value), ...].

		The list view passes a `Filters` object (list of 4-tuples), a list of lists, or a
		{field: value} / {field: [op, value]} dict. We keep only filters on fields that
		actually exist on the row (drops standard-field filters like `modified`).
		"""
		out = []
		if not filters:
			return out
		known = cls._field_set()
		if isinstance(filters, dict):
			items = []
			for field, spec in filters.items():
				if isinstance(spec, (list, tuple)) and len(spec) == 2:
					items.append((field, spec[0], spec[1]))
				else:
					items.append((field, "=", spec))
			seq = items
		else:
			seq = filters
		for f in seq:
			f = tuple(f)
			if len(f) == 4:  # (doctype, field, op, value)
				_, field, op, value = f
			elif len(f) == 3:  # (field, op, value)
				field, op, value = f
			elif len(f) == 2:  # (field, value)
				field, op, value = f[0], "=", f[1]
			else:
				continue
			if field in known:
				out.append((field, (op or "=").lower(), value))
		return out

	@staticmethod
	def _matches(cell, op: str, value) -> bool:
		"""Evaluate one filter operator against a single row value (local filtering)."""
		if op in ("=", "=="):
			return str(cell) == str(value)
		if op in ("!=", "not ="):
			return str(cell) != str(value)
		if op in ("like", "not like"):
			needle = str(value).strip("%").lower()
			hit = needle in (str(cell).lower() if cell is not None else "")
			return hit if op == "like" else not hit
		if op in ("in", "not in"):
			options = value if isinstance(value, (list, tuple, set)) else str(value).split(",")
			options = {str(v).strip() for v in options}
			hit = str(cell) in options
			return hit if op == "in" else not hit
		if op == "is":
			empty = cell in (None, "")
			return empty if str(value) == "not set" else not empty
		if op in (">", "<", ">=", "<="):
			try:
				a, b = float(cell), float(value)
			except (TypeError, ValueError):
				a, b = str(cell), str(value)
			return {
				">": a > b, "<": a < b, ">=": a >= b, "<=": a <= b,
			}[op]
		return True  # unknown operator -> don't filter out

	@classmethod
	def _apply_filters(cls, rows: list, filters: list) -> list:
		for field, op, value in filters:
			rows = [r for r in rows if cls._matches(r.get(field), op, value)]
		return rows

	@classmethod
	def _parse_order_by(cls, order_by) -> list:
		"""`` `tabX`.`field` desc, ... `` -> [(field, reverse_bool)] for real fields only."""
		if not order_by or order_by == "KEEP_DEFAULT_ORDERING":
			return []
		known = cls._field_set()
		specs = []
		for segment in str(order_by).split(","):
			seg = segment.strip()
			if not seg:
				continue
			# Direction is a trailing asc/desc token; strip it before reading the field.
			reverse = bool(re.search(r"\bdesc\s*$", seg, re.IGNORECASE))
			seg = re.sub(r"\s+(asc|desc)\s*$", "", seg, flags=re.IGNORECASE)
			# Field may be `tabMarzi User`.`first_name` (backtick-quoted, spaces inside).
			quoted = re.findall(r"`([^`]+)`", seg)
			field = quoted[-1] if quoted else seg.split(".")[-1].strip().strip("`")
			if field in known:
				specs.append((field, reverse))
		return specs

	@classmethod
	def _apply_order_by(cls, rows: list, order_by) -> list:
		for field, reverse in reversed(cls._parse_order_by(order_by)):
			rows.sort(
				key=lambda r: (r.get(field) is None, cls._sort_key(r.get(field))),
				reverse=reverse,
			)
		return rows

	@staticmethod
	def _sort_key(value):
		"""Numbers sort numerically, everything else case-insensitively as text."""
		if isinstance(value, (int, float)):
			return value
		try:
			return float(value)
		except (TypeError, ValueError):
			return str(value).lower()

	@classmethod
	def _api_list(cls, filters=None, start=0, page_length=20, order_by=None, **kwargs):
		try:
			start, page_length = int(start or 0), int(page_length or 0)
		except (TypeError, ValueError):
			start, page_length = 0, 0
		norm_filters = cls._normalize_filters(filters)
		order_specs = cls._parse_order_by(order_by)
		# Filtering/sorting need the whole set; otherwise stop paging as soon as we have
		# enough rows for this page (keeps first-load fast for cursor-paginated entities).
		need = None if (norm_filters or order_specs) else ((start + page_length) if page_length else None)
		rows = [cls._to_row(obj) for obj in cls._fetch_collection(need=need)]
		rows = cls._apply_filters(rows, norm_filters)
		rows = cls._apply_order_by(rows, order_by)
		# Backends return whole collections (or cursor pages); slice locally.
		return rows[start : start + page_length] if page_length else rows[start:]

	@classmethod
	def _api_count(cls, filters=None, **kwargs) -> int:
		norm_filters = cls._normalize_filters(filters)
		# When the list view has active filters, the count must reflect them (the
		# "X of Y" footer / pagination). Compute fresh from the full collection; don't
		# cache (the unfiltered cache below would be wrong for a filtered request).
		if norm_filters:
			rows = [cls._to_row(obj) for obj in cls._fetch_collection()]
			return len(cls._apply_filters(rows, norm_filters))
		# Counting a cursor-paginated collection walks every page — cache briefly so
		# each list-view refresh doesn't re-walk the backend.
		if cls.api_cursor_key:
			key = f"marzi_bridge_count::{cls.DOCTYPE}"
			cached = frappe.cache.get_value(key)
			if cached is not None:
				return int(cached)
			count = len(cls._fetch_collection())
			frappe.cache.set_value(key, count, expires_in_sec=120)
			return count
		return len(cls._fetch_collection())

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
			# Some detail shapes omit list-row fields (GET /users/<id> has no
			# phone/email/role); merge the list row underneath, detail winning.
			if self.api_detail_merge_list and isinstance(obj, dict):
				try:
					list_row = self._find_in_list(self.name)
				except Exception:  # noqa: BLE001 — merge is best-effort
					list_row = None
				if list_row:
					obj = {**list_row, **obj}
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
		# Flatten nested backend objects onto their flat form fields (inverse of the
		# write assembly), so e.g. meta.title -> meta_title, heroImage.url -> hero_image_url.
		fieldtypes = {df.fieldname: df.fieldtype for df in frappe.get_meta(self.DOCTYPE).fields}
		for backend_key, subspec in {**self.api_read_nested, **self.api_nested_fields}.items():
			self._flatten_nested(row, obj.get(backend_key), subspec, fieldtypes)
		# Standard metadata Frappe's save/concurrency flow expects on a loaded doc
		# (virtual docs have no table, so supply sensible values from the backend).
		now = frappe.utils.now()
		row.setdefault("creation", obj.get("created_at") or obj.get("createdAt") or now)
		row.setdefault("modified", obj.get("updated_at") or obj.get("updatedAt") or now)
		row.setdefault("owner", "Administrator")
		row.setdefault("modified_by", "Administrator")
		row.setdefault("docstatus", 0)
		row.setdefault("idx", 0)
		super(Document, self).__init__(row)

	def _flatten_nested(self, row: dict, value, subspec: dict, fieldtypes: dict):
		"""Spread a nested backend object across its flat frappe fields (detail read).

		Lists/dicts destined for a Code/JSON field are serialized, matching _map_obj.
		"""
		value = value if isinstance(value, dict) else {}
		for sub_key, ref in subspec.items():
			if isinstance(ref, dict):
				self._flatten_nested(row, value.get(sub_key), ref, fieldtypes)
				continue
			sub_value = value.get(sub_key)
			if sub_value is None:
				continue
			if fieldtypes.get(ref) in _JSON_FIELDTYPES and isinstance(sub_value, (dict, list)):
				sub_value = json.dumps(sub_value, indent=2, default=str, ensure_ascii=False)
			row[ref] = sub_value

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
		for obj in cls._fetch_collection():
			if str((obj or {}).get(cls.api_id_field)) == str(record_id):
				return obj
		return None

	@classmethod
	def _write_base(cls) -> str:
		return cls.api_write_endpoint or cls.api_endpoint

	def _write_id(self):
		return self.get(self.api_write_id_field) if self.api_write_id_field else self.name

	def db_insert(self, *args, **kwargs):
		if not self.api_write_fields or not self.api_can_create:
			frappe.throw(_("{0} cannot be created here.").format(_(self.DOCTYPE)), exc=MarziAPIError)
		data = MarziClient().post(
			self._write_base(), service=self.api_service, auth=self.api_auth, json_body=self._to_body()
		)
		obj = self._unwrap_item(data) or {}
		new_id = obj.get(self.api_write_id_field or self.api_id_field)
		if new_id:
			self.name = new_id

	def db_update(self, *args, **kwargs):
		if not self.api_write_fields:
			frappe.throw(_("{0} is read-only.").format(_(self.DOCTYPE)), exc=MarziAPIError)
		client = MarziClient()
		caller = client.put if self.api_update_method.upper() == "PUT" else client.patch
		caller(
			f"{self._write_base()}/{self._write_id()}",
			service=self.api_service,
			auth=self.api_auth,
			json_body=self._to_body(),
		)

	def delete(self, *args, **kwargs):
		if not self.api_can_delete:
			frappe.throw(_("{0} cannot be deleted here.").format(_(self.DOCTYPE)), exc=MarziAPIError)
		MarziClient().delete(
			f"{self._write_base()}/{self._write_id()}", service=self.api_service, auth=self.api_auth
		)
