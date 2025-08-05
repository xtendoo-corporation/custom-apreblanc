# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class OneDriveSyncSummary(models.TransientModel):
    _name = 'onedrive.sync.summary'
    _description = 'Resumen de Sincronización OneDrive'

    name = fields.Char('Título', default='Resultado de la Sincronización')
    synced_count = fields.Integer('Elementos procesados', readonly=True)
    created_count = fields.Integer('Elementos creados', readonly=True)
    updated_count = fields.Integer('Elementos actualizados', readonly=True)
    success = fields.Boolean('Éxito', readonly=True)
    error_message = fields.Text('Mensaje de error', readonly=True)

    def action_close(self):
        """Cerrar el wizard y recargar la vista"""
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
