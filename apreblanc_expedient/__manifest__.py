{
    'name': 'Apreblanc Expedient',
    'version': '17.0.1.0.0',
    'category': 'Administration',
    'summary': 'Expedient management module',
    'author': 'Xtendoo Software SLU',
    'website': 'https://www.xtendoo.es',
    'license': 'AGPL-3',
    'depends': ['base', 'mail'],
    'data': [
        'data/apreblanc_expedient_sequence.xml',
        'security/ir.model.access.csv',
        'views/apreblanc_expedient_views.xml',
        'views/apreblanc_expedient_return_views.xml',
    ],
    'installable': True,
    'application': True,
}
