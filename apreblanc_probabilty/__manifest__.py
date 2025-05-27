{
    'name': 'Probabilidad en Pedidos de Venta',
    'version': '17.0.1.0.0',
    'category': 'Sales',
    'summary': 'Añade campo de probabilidad a los pedidos de venta',
    'author':  'Xtendoo',
    'website': 'http://www.xtendoo.es',
    'license': 'AGPL-3',
    'depends': [
        'sale',
        'sale_margin',
        'sale_management'
    ],
    'data': [
        'report/sale_report_views.xml',
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
