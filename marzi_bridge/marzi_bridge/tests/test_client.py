"""Unit tests for MarziClient.

Run under a bench site: `bench --site <site> run-tests --app marzi_bridge`.
The backend session and the token layer are mocked, so these tests never make a
real network call and do not need a linked account.
"""

import unittest
from unittest.mock import MagicMock, patch

import frappe

from marzi_bridge import client as client_mod
from marzi_bridge.client import MarziAPIError, MarziClient


class FakeResponse:
	def __init__(self, status_code, json_body=None, text="", content_type="application/json"):
		self.status_code = status_code
		self._json = json_body
		self.text = text
		self.headers = {"content-type": content_type}

	def json(self):
		if self._json is None:
			raise ValueError("no json")
		return self._json


def _settings():
	values = {
		"v1_base_url": "https://api.example.com/v1",
		"v3_base_url": "https://api.example.com/v1/v3",
		"publishing_base_url": "https://api.example.com",
		"blog_base_url": "https://blog.example.com",
		"tracking_base_url": "https://track.example.com",
		"whatsapp_base_url": "https://wa.example.com",
		"payments_base_url": "https://pay.example.com",
		"request_timeout": 30,
		"verify_tls": 1,
	}
	s = MagicMock()
	s.configure_mock(**values)
	# MarziClient reads base URLs via settings.get(field); back it by the same dict.
	s.get.side_effect = values.get
	return s


class MarziClientTests(unittest.TestCase):
	def setUp(self):
		p = patch.object(client_mod, "get_settings", return_value=_settings())
		p.start()
		self.addCleanup(p.stop)

		for target, value in (
			("marzi_bridge.auth.tokens.get_valid_token", "tok-1"),
			("marzi_bridge.auth.tokens.force_refresh", "tok-2"),
		):
			tp = patch(target, return_value=value)
			tp.start()
			self.addCleanup(tp.stop)

	def _with_session(self, *responses):
		session = MagicMock()
		session.request.side_effect = list(responses)
		return session, patch.object(client_mod, "get_request_session", return_value=session)

	def test_builds_url_and_attaches_bearer(self):
		session, sp = self._with_session(FakeResponse(200, {"ok": True}))
		with sp:
			out = MarziClient(user="a@example.com").get("/speakers", params={"page": 1})
		self.assertEqual(out, {"ok": True})
		args, kwargs = session.request.call_args
		self.assertEqual(args[0], "GET")
		self.assertEqual(args[1], "https://api.example.com/v1/speakers")
		self.assertEqual(kwargs["headers"]["Authorization"], "Bearer tok-1")
		self.assertEqual(kwargs["params"], {"page": 1})
		self.assertEqual(kwargs["timeout"], 30)
		self.assertTrue(kwargs["verify"])

	def test_v3_base_url_used(self):
		session, sp = self._with_session(FakeResponse(200, {}))
		with sp:
			MarziClient(user="a@example.com").get("/admin/events", version="v3")
		self.assertEqual(
			session.request.call_args[0][1], "https://api.example.com/v1/v3/admin/events"
		)

	def test_service_selects_mapped_base_url(self):
		session, sp = self._with_session(FakeResponse(200, {}))
		with sp:
			MarziClient(user="a@example.com").get("/admin/posts", service="blog")
		self.assertEqual(session.request.call_args[0][1], "https://blog.example.com/admin/posts")

	def test_auth_false_omits_token_and_skips_refresh(self):
		# whatsapp/payments are called unauthenticated by the dashboard. When
		# auth=False, no token is attached and the token layer is never touched.
		session, sp = self._with_session(FakeResponse(200, {"ok": 1}))
		with sp, patch("marzi_bridge.auth.tokens.get_valid_token") as gvt, patch(
			"marzi_bridge.auth.tokens.force_refresh"
		) as fr:
			out = MarziClient(user="a@example.com").get(
				"/payment/all", service="payments", auth=False
			)
		self.assertEqual(out, {"ok": 1})
		gvt.assert_not_called()
		fr.assert_not_called()
		self.assertNotIn("Authorization", session.request.call_args.kwargs["headers"])
		self.assertEqual(session.request.call_args[0][1], "https://pay.example.com/payment/all")

	def test_401_triggers_single_refresh_and_retry(self):
		session, sp = self._with_session(
			FakeResponse(401, {"message": "expired"}), FakeResponse(200, {"ok": 1})
		)
		with sp:
			out = MarziClient(user="a@example.com").get("/speakers")
		self.assertEqual(out, {"ok": 1})
		self.assertEqual(session.request.call_count, 2)
		self.assertEqual(
			session.request.call_args_list[1].kwargs["headers"]["Authorization"], "Bearer tok-2"
		)

	def test_401_twice_raises(self):
		session, sp = self._with_session(
			FakeResponse(401, {"message": "no"}), FakeResponse(401, {"message": "still no"})
		)
		with sp, patch.object(frappe, "log_error"):
			with self.assertRaises(MarziAPIError):
				MarziClient(user="a@example.com").get("/speakers")
		self.assertEqual(session.request.call_count, 2)

	def test_error_is_normalized_and_token_not_logged(self):
		session, sp = self._with_session(FakeResponse(422, {"message": "bad input"}))
		with sp, patch.object(frappe, "log_error") as log:
			with self.assertRaises(MarziAPIError):
				MarziClient(user="a@example.com").post("/speakers", json_body={"x": 1})
		log.assert_called_once()
		self.assertNotIn("tok-1", str(log.call_args))
