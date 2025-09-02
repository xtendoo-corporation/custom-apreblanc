# -*- coding: utf-8 -*-
# Copyright 2025 Xtendoo Software
# License GPL-3.0 or later (http://www.gnu.org/licenses/gpl.html)

from odoo import models, fields, api


class SaleExporterImporter(models.TransientModel):
    _name = 'sale.exporter.importer'
    _description = 'Sale Exporter Importer Configuration'

    @api.model
    def open_export_wizard(self):
        """Open the export wizard"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Exportar Todas las Ventas',
            'res_model': 'sale.export.wizard',
            'view_mode': 'form',
            'target': 'new',
        }

    @api.model
    def open_import_wizard(self):
        """Open the import wizard"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Importar Todas las Ventas',
            'res_model': 'sale.import.wizard',
            'view_mode': 'form',
            'target': 'new',
        }
