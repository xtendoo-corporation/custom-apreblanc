{
    'name': 'Sale Order Expedient',
    'version': '17.0.1.0.0',
    'category': 'Sales',
    'summary': 'Adds expedient management to sales orders',
    'author': 'Xtendoo Software SLU,' 'José Aguilar',
    'website': 'https://www.xtendoo.es',
    'license': 'AGPL-3',
    'depends': ['sale', 'sale_management', 'mail'],
    'data': [
        # Seguridad primero
        'security/security.xml',  # Archivo de seguridad
        'security/ir.model.access.csv',

        # Datos
        'data/ir_sequence_data.xml',
        'data/ir_cron.xml',

        # Wizards
        'wizards/expedient_wizard_views.xml',
        'wizards/expedient_create_wizard_views.xml',

        # Vistas de modelos base
        'views/expedient_return_reason_views.xml',
        'views/sale_order_template_views.xml',
        'views/expedient_views.xml',  # Primero cargar vistas base de expedientes
        'views/sale_order_views.xml',  # Luego las vistas de sale.order
        'views/sale_order_template_wizard_views.xml',
        'views/sale_order_prepaid_views.xml',
        'views/expedient_wizard_new_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'sale_order_expedient/static/src/js/sale_order_create_hook.js',
            'sale_order_expedient/static/src/js/expedient_statusbar_fix.js',
            'sale_order_expedient/static/src/css/expedient_styles.css',
        ],
    },
    'installable': True,
    'application': False,
}
