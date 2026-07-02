{
    "name": "Apreblanc Chatter Filter",
    "version": "17.0.3.0.0",
    "category": "Accounting",
    "summary": "Filtra mensajes económicos en el chatter por grupo de contabilidad",
    "author": "Xtendoo / XTD",
    "website": "http://www.xtendoo.es",
    "license": "LGPL-3",
    "depends": [
        "mail",
        "account",
        "sale",
    ],
    "data": [
        "data/res_groups.xml",
        "data/mail_message_subtype.xml",
        "security/mail_message_rules.xml",
    ],
    "installable": True,
    "application": False,
}
