{
    "name": "xtendoo_onedrive_connector",
    "version": "17.0.1.0.0",
    "category": "Tools",
    "summary": "Conector Odoo con OneDrive para ver, subir y descargar documentos.",
    "author": "Tu Empresa / Xtendoo",
    "website": "https://www.xtendoo.es/",
    "depends": ["base"],
    "data": [
        "security/ir.model.access.csv",
        "data/server_actions.xml",
        "views/onedrive_document_views.xml",
        "views/onedrive_callback_template.xml",
        "views/onedrive_menu_views.xml",
        "views/res_config_settings_views.xml",
        "views/settings_menu_views.xml",
        "views/onedrive_sync_summary_views.xml",
        "menu.xml"
    ],
    "assets": {
        "web.assets_backend": [
            "xtendoo_onedrive_connector/static/src/js/sale_context_extractor.js",
        ],
    },
    "installable": "true",
    "application": "true",
    "license": "LGPL-3"
}
