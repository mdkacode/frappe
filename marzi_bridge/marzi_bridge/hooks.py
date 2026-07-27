app_name = "marzi_bridge"
app_title = "Marzi Bridge"
app_publisher = "Spreetail"
app_description = "Server-side proxy from Frappe to the Backend-for-org (marzi) /v1 & /v3 APIs."
app_email = "prabhas.mudhiveti@spreetail.com"
app_license = "MIT"

# Branding — replace the Frappe marks with Marzi's
# ------------------------------------------------------------------------------
# Navbar + login page logo (get_app_logo falls back to this hook when neither
# Website Settings nor Navbar Settings sets app_logo).
app_logo_url = "/assets/marzi_bridge/images/marzi-logo.png"

# Favicon + login splash (merged into the website render context).
website_context = {
	"favicon": "/assets/marzi_bridge/images/marzi-favicon.png",
	"splash_image": "/assets/marzi_bridge/images/marzi-logo.png",
}

# Desk CSS/JS: Marzi branding + the record overview header on every Marzi Form.
# /assets/... paths are served with long-lived cache headers, so bump ?v= on every
# change to these files — otherwise browsers keep the stale copy.
app_include_css = "/assets/marzi_bridge/css/marzi_branding.css?v=7"
app_include_js = "/assets/marzi_bridge/js/marzi_overview.js?v=5"

# Roles / setup
# ------------------------------------------------------------------------------
after_install = "marzi_bridge.install.after_install"

# Fixtures — export the base role so it travels with the app
# ------------------------------------------------------------------------------
fixtures = [
	{"dt": "Role", "filters": [["role_name", "in", ["Marzi Admin"]]]},
]

# Show Marzi Bridge as its own tile on the /apps launcher (opens its workspace)
# ------------------------------------------------------------------------------
add_to_apps_screen = [
	{
		"name": "marzi_bridge",
		"logo": "/assets/marzi_bridge/images/marzi-favicon.png",
		"title": "Marzi Bridge",
		# Land on the (API-backed) Marzi User list — the app's home screen.
		"route": "/desk/marzi-user",
		"has_permission": "marzi_bridge.permissions.check_app_permission",
	}
]
