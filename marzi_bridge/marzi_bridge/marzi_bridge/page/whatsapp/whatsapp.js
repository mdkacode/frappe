// Marzi Bridge — WhatsApp desk page.
//
// A WhatsApp-style two-pane chat over the whatsapp Lambda (mirrors admin-v2's
// whatsapp-chat.tsx). Left = conversation list, right = message thread + composer.
// Data flows through the existing whitelisted proxies (marzi_bridge.api.whatsapp.*):
// list_conversations / get_messages / send_message. The whatsapp service is called
// unauthenticated upstream (auth=False) — matching the dashboard — so no token juggling.

frappe.provide("marzi");

frappe.pages["whatsapp"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("WhatsApp"),
		single_column: true,
	});
	wrapper.__marzi_wa = new marzi.WhatsApp(page, wrapper);
};

frappe.pages["whatsapp"].on_page_show = function (wrapper) {
	wrapper.__marzi_wa && wrapper.__marzi_wa.start();
};

frappe.pages["whatsapp"].on_page_hide = function (wrapper) {
	wrapper.__marzi_wa && wrapper.__marzi_wa.stop();
};

marzi.WhatsApp = class WhatsApp {
	constructor(page) {
		this.page = page;
		this.conversations = [];
		this.selected = null;
		this.messages = [];
		this.msgCount = -1;
		this.convTimer = null;
		this.msgTimer = null;
		this.render_shell();
	}

	start() {
		if (this.convTimer) return;
		this.load_conversations();
		this.convTimer = setInterval(() => !document.hidden && this.load_conversations(), 10000);
		this.msgTimer = setInterval(() => {
			if (!document.hidden && this.selected) this.load_messages();
		}, 5000);
	}

	stop() {
		clearInterval(this.convTimer);
		clearInterval(this.msgTimer);
		this.convTimer = this.msgTimer = null;
	}

	// ---- data ----------------------------------------------------------------
	async load_conversations() {
		try {
			const r = await frappe.call({
				method: "marzi_bridge.api.whatsapp.list_conversations",
				args: { limit: 80 },
				silent: true,
			});
			this.conversations = marzi.wa_items(r && r.message, "conversations");
			this.render_list();
		} catch (e) {
			/* transient */
		}
	}

	async load_messages() {
		if (!this.selected) return;
		try {
			const r = await frappe.call({
				method: "marzi_bridge.api.whatsapp.get_messages",
				args: { mobile: this.selected, limit: 200 },
			});
			const msgs = marzi
				.wa_items(r && r.message, "messages")
				.slice()
				.sort((a, b) => marzi.wa_ts(a) - marzi.wa_ts(b));
			this.messages = msgs;
			this.render_thread();
		} catch (e) {
			// Surface the failure in the thread instead of silently showing an empty chat.
			const $t = this.page.main.find('[data-k="thread"]');
			if ($t.length) {
				$t.html(
					`<div class="wa-empty">Couldn't load messages.<br><small>${frappe.utils.escape_html(
						(e && (e.message || e.responseText)) || String(e)
					)}</small></div>`
				);
			}
		}
	}

	async send() {
		const $inp = this.page.main.find(".wa-input");
		const body = ($inp.val() || "").trim();
		if (!body || !this.selected) return;
		$inp.val("").prop("disabled", true);
		try {
			await frappe.call({
				method: "marzi_bridge.api.whatsapp.send_message",
				args: { mobile: this.selected, body },
			});
			await this.load_messages();
		} catch (e) {
			$inp.val(body); // restore on failure (error already shown by frappe)
		} finally {
			$inp.prop("disabled", false).focus();
		}
	}

	select(mobile) {
		this.selected = mobile;
		this.messages = [];
		this.msgCount = -1;
		this.render_list(); // update active highlight
		this.render_chat_shell();
		this.load_messages();
	}

	// ---- render --------------------------------------------------------------
	render_shell() {
		this.page.main.html(`
			<div class="marzi-wa">
				<div class="wa-list">
					<div class="wa-list-head">Chats</div>
					<div class="wa-list-body" data-k="convs"></div>
				</div>
				<div class="wa-chat" data-k="chat">
					<div class="wa-empty">Select a conversation to view messages</div>
				</div>
			</div>
		`);
		// Delegated click — survives the 10s list re-render (direct handlers would be lost).
		// attr() (not .data()) keeps the mobile an exact string, no numeric coercion.
		this.page.main.on("click", ".wa-conv", (e) => {
			const mobile = $(e.currentTarget).attr("data-mobile");
			try {
				this.select(mobile);
			} catch (err) {
				this.page.main.find('[data-k="chat"]').html(
					`<div class="wa-empty">Error opening chat: ${frappe.utils.escape_html(String(err))}</div>`
				);
			}
		});
	}

	render_list() {
		const esc = frappe.utils.escape_html;
		const rows = this.conversations
			.slice()
			.sort((a, b) => marzi.wa_conv_time(b) - marzi.wa_conv_time(a))
			.map((c) => {
				const name = marzi.wa_name(c);
				const preview = esc(c.lastMessage || c.lastMessageText || c.lastMessageBody || "");
				const t = marzi.wa_conv_time(c);
				return `<div class="wa-conv ${c.mobile === this.selected ? "is-active" : ""}" data-mobile="${esc(c.mobile)}">
					<div class="wa-avatar">${esc(name.slice(0, 1).toUpperCase() || "?")}</div>
					<div class="wa-conv-body">
						<div class="wa-conv-top"><span class="wa-conv-name">${esc(name)}</span>
							<span class="wa-conv-time">${t ? marzi.wa_ago(t) : ""}</span></div>
						<div class="wa-conv-preview">${preview || "&nbsp;"}</div>
					</div>
				</div>`;
			})
			.join("");
		const $c = this.page.main.find('[data-k="convs"]');
		$c.html(rows || `<div class="wa-empty">No conversations.</div>`);
		// click handling is delegated in render_shell (survives re-renders)
	}

	render_chat_shell() {
		const conv = this.conversations.find((c) => c.mobile === this.selected) || { mobile: this.selected };
		const esc = frappe.utils.escape_html;
		const name = marzi.wa_name(conv);
		this.page.main.find('[data-k="chat"]').html(`
			<div class="wa-chat-head">
				<div class="wa-avatar">${esc(name.slice(0, 1).toUpperCase() || "?")}</div>
				<div><div class="wa-chat-name">${esc(name)}</div>
					<div class="wa-chat-sub">${esc(marzi.wa_phone(conv.mobile))}</div></div>
			</div>
			<div class="wa-thread" data-k="thread"><div class="wa-empty">Loading…</div></div>
			<div class="wa-compose">
				<input type="text" class="wa-input" placeholder="Type a message" />
				<button class="wa-send btn btn-primary">Send</button>
			</div>
		`);
		this.page.main.find(".wa-send").on("click", () => this.send());
		this.page.main.find(".wa-input").on("keydown", (e) => {
			if (e.key === "Enter") this.send();
		});
		this.apply_send_window();
	}

	render_thread() {
		const $t = this.page.main.find('[data-k="thread"]');
		if (!$t.length) return;
		const esc = frappe.utils.escape_html;
		if (!this.messages.length) {
			$t.html(`<div class="wa-empty">No messages yet.</div>`);
			return;
		}
		let html = "";
		let lastDate = "";
		for (const m of this.messages) {
			const ts = marzi.wa_ts(m);
			const dateStr = marzi.wa_date_sep(ts);
			if (dateStr !== lastDate) {
				html += `<div class="wa-datesep"><span>${esc(dateStr)}</span></div>`;
				lastDate = dateStr;
			}
			const inbound = String(m.direction || "inbound").toLowerCase() === "inbound";
			const text = esc(m.messageText || m.body || "");
			html += `<div class="wa-msg ${inbound ? "in" : "out"}">
				<div class="wa-bubble">${text}<span class="wa-time">${ts ? marzi.wa_clock(ts) : ""}</span></div>
			</div>`;
		}
		// preserve scroll position unless new messages arrived
		const grew = this.messages.length !== this.msgCount;
		this.msgCount = this.messages.length;
		$t.html(html);
		if (grew) $t.scrollTop($t[0].scrollHeight);
		this.apply_send_window();
	}

	// WhatsApp only allows free-form replies within 24h of the user's last inbound.
	apply_send_window() {
		let lastInbound = 0;
		for (const m of this.messages) {
			if (String(m.direction || "inbound").toLowerCase() === "inbound") {
				lastInbound = Math.max(lastInbound, marzi.wa_ts(m));
			}
		}
		const open = lastInbound && Date.now() - lastInbound < 24 * 3600 * 1000;
		const $inp = this.page.main.find(".wa-input");
		const $btn = this.page.main.find(".wa-send");
		if (this.messages.length && !open) {
			$inp.prop("disabled", true).attr("placeholder", "Outside the 24h reply window");
			$btn.prop("disabled", true);
		} else {
			$inp.prop("disabled", false).attr("placeholder", "Type a message");
			$btn.prop("disabled", false);
		}
	}
};

// ---- helpers ----------------------------------------------------------------
marzi.wa_items = function (res, alt) {
	if (!res) return [];
	const d = res.data || res;
	return d.items || d[alt] || res.items || res[alt] || [];
};
marzi.wa_name = function (c) {
	return (
		c.name || c.fullName || c.userName ||
		(c.userProfile && c.userProfile.name) || (c.stepData && c.stepData.name) ||
		marzi.wa_phone(c.mobile)
	);
};
marzi.wa_phone = function (mobile) {
	mobile = String(mobile || "");
	if (mobile.startsWith("91") && mobile.length === 12)
		return `+91 ${mobile.slice(2, 7)} ${mobile.slice(7)}`;
	return mobile ? "+" + mobile : "";
};
marzi.wa_norm_ts = function (v) {
	if (v == null) return 0;
	const n = typeof v === "string" ? Number(v) : v;
	if (isNaN(n)) return 0;
	return n < 1e12 ? n * 1000 : n; // seconds → ms
};
marzi.wa_ts = function (m) {
	return marzi.wa_norm_ts(m.timestamp) || marzi.wa_norm_ts(m.createdAt) || marzi.wa_norm_ts(m.sentAt) || 0;
};
marzi.wa_conv_time = function (c) {
	return marzi.wa_norm_ts(c.lastInteraction) || marzi.wa_norm_ts(c.lastInteractionDate) || marzi.wa_norm_ts(c.timestamp) || 0;
};
marzi.wa_clock = function (ts) {
	return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
};
marzi.wa_date_sep = function (ts) {
	const d = new Date(ts), now = new Date();
	const same = (a, b) => a.toDateString() === b.toDateString();
	if (same(d, now)) return "Today";
	const y = new Date(now); y.setDate(now.getDate() - 1);
	if (same(d, y)) return "Yesterday";
	return d.toLocaleDateString([], { day: "numeric", month: "short", year: "numeric" });
};
marzi.wa_ago = function (ts) {
	const s = Math.max(0, Math.round((Date.now() - ts) / 1000));
	if (s < 60) return "now";
	const m = Math.round(s / 60);
	if (m < 60) return m + "m";
	const h = Math.round(m / 60);
	if (h < 24) return h + "h";
	return marzi.wa_date_sep(ts);
};
