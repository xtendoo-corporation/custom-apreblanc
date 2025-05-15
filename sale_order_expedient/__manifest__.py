{
    'name': 'Sale Order Expedient',
    'version': '17.0.1.0.0',
    'category': 'Sales',
    'summary': 'Añade gestión de expedientes a órdenes de venta',
    'author': 'Xtendoo Software SLU',
    'website': 'https://www.xtendoo.es',
    'license': 'AGPL-3',
    'depends': ['sale', 'sale_management'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'wizards/expedient_wizard_views.xml',
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'application': False,
}
