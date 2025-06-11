{
    'name': 'Sale Order Expedient',
    'version': '17.0.1.0.0',
    'category': 'Sales',
    'summary': 'Adds expedient management to sales orders',
    'author': 'Xtendoo Software SLU',
    'website': 'https://www.xtendoo.es',
    'license': 'AGPL-3',
    'depends': ['sale', 'sale_management', 'mail'],
    'data': [
        # Seguridad primero
        'security/ir.model.access.csv',

        # Datos
        'data/ir_sequence_data.xml',
        'data/ir_cron.xml',

        # Wizards (movidos al principio para evitar dependencias circulares)
        'wizards/expedient_wizard_views.xml',
        'wizards/expedient_create_wizard_views.xml',

        # Vistas de modelos base
        'views/expedient_return_reason_views.xml',
        'views/sale_order_template_views.xml',
        'views/sale_order_views.xml',
        'views/sale_order_template_wizard_views.xml',

        # Vistas de expedientes prepagados
        'views/sale_order_views.xml',
        'views/sale_order_prepaid_views.xml',
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
