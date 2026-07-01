{
    "name": "Apreblanc Expedient Report",
    "version": "17.0.3.0.0",
    "category": "Sales/Reporting",
    "summary": "Expedientes con visualización de mensajes del chatter",
    "author": "Xtendoo",
    "website": "http://www.xtendoo.es",
    "license": "AGPL-3",

    "depends": ["sale", "mail"],

    "data": [
        "security/ir.model.access.csv",
        "views/expedient_report_views.xml",
        "views/menu_views.xml",
    ],

    "installable": True,
    "application": False,
}
