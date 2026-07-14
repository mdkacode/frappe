app_name = "marzi_bridge"
app_title = "Marzi Bridge"
app_publisher = "Spreetail"
app_description = "Server-side proxy from Frappe to the Backend-for-org (marzi) /v1 & /v3 APIs."
app_email = "prabhas.mudhiveti@spreetail.com"
app_license = "MIT"

# Roles / setup
# ------------------------------------------------------------------------------
after_install = "marzi_bridge.install.after_install"

# Fixtures — export the base role so it travels with the app
# ------------------------------------------------------------------------------
fixtures = [
	{"dt": "Role", "filters": [["role_name", "in", ["Marzi Admin"]]]},
]
