# -*- coding: utf-8 -*-
# Copyright 2025 Xtendoo Software
# License GPL-3.0 or later (http://www.gnu.org/licenses/gpl.html)

{
    'name': 'Sale Exporter Importer',
    'version': '17.0.1.0.0',
    'category': 'Sales',
    'summary': 'Export and import sales data with related tables to/from Excel files',
    'description': '''
    Sale Exporter Importer
    ======================

    This module provides functionality to:
    * Export all sales with their related tables to Excel files
    * Import sales data from Excel files to the database

    Features:
    * Export all sales orders with related data
    * Import sales orders from Excel files
    * Configuration menu in Sales settings
    ''',
    'author': 'Xtendoo Software ',
    'website': 'https://www.xtendoo.es',
    'license': 'GPL-3',
    'depends': [
        'base',
        'sale',
        'sale_management',
    ],
    'data': [
        'security/ir.model.access.csv',
        'wizard/sale_export_wizard_views.xml',
        'wizard/sale_import_wizard_views.xml',
        'views/sale_exporter_importer_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
