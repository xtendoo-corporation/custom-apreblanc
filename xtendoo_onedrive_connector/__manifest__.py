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
        "views/onedrive_document_views.xml",
        "views/onedrive_callback_template.xml"
    ],
    "installable": "true",
    "application": "true",
    "license": "LGPL-3"
}
