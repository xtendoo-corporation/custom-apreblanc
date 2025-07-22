{
    'name': 'Apreblanc Sale Order Expedient',
    'version': '17.0.1.0.0',
    'category': 'Sales',
    'summary': 'Adds expedient management to sales orders for Apreblanc',
    'author': 'Xtendoo Software SLU,' 'José Aguilar',
    'website': 'https://www.xtendoo.es',
    'license': 'AGPL-3',
    'depends': ['sale', 'sale_management', 'mail'],
    'external_dependencies': {
        'python': ['xlrd'],
    },
    'data': [
        # Seguridad primero
        'security/security.xml',  # Archivo de seguridad
        'security/sale_order_template_security.xml',  # Nueva regla de seguridad para plantillas
        'security/ir.model.access.csv',  # Archivo principal de reglas de acceso

        # Datos
        'data/ir_sequence_data.xml',
        'data/ir_cron.xml',
        'data/cron_data.xml',
        'data/expedient_return_reason_data.xml',  # Datos iniciales para motivos de devolución

        # Wizards
        'wizards/expedient_create_wizard_views.xml',
        'wizards/import_expedient_excel_view.xml',  # Nuevo asistente de importación Excel

        # Vistas de modelos base
        'views/sale_order_search_views.xml',
        'views/sale_order_template_views.xml',
        'views/expedient_views.xml',  # Primero cargar vistas base de expedientes
        'views/sale_order_views.xml',  # Luego las vistas de sale.order
        'views/sale_order_template_wizard_views.xml',
        # 'views/pre_paid_expedient_views.xml',
        #'views/expedient_wizard_new_views.xml',

    ],
    'assets': {
        'web.assets_backend': [
            'apreblanc_sale_order_expedient/static/src/js/sale_order_create_hook.js',
            'apreblanc_sale_order_expedient/static/src/js/expedient_statusbar_fix.js',
            'apreblanc_sale_order_expedient/static/src/css/expedient_styles.css',
        ],
    },
    'installable': True,
    'application': False,
}
