# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import base64

class OneDriveDocument(models.Model):
    _name = 'onedrive.document'
    _description = 'Documento de OneDrive'

    name = fields.Char('Nombre', required=True)
    onedrive_id = fields.Char('ID OneDrive', required=True, index=True)
    file_url = fields.Char('URL de archivo')
    file_size = fields.Integer('Tamaño (bytes)')
    file_type = fields.Char('Tipo')
    owner = fields.Char('Propietario')
    last_modified = fields.Datetime('Última modificación')
    file_data = fields.Binary('Archivo descargado', readonly=True)
    upload_file = fields.Binary('Subir archivo')
    upload_filename = fields.Char('Nombre de archivo a subir')

    def action_download_file(self):
        service = self.env['onedrive.service']
        for rec in self:
            if not rec.onedrive_id:
                raise UserError(_('No hay ID de OneDrive para este documento.'))
            content = service.download_file(rec.onedrive_id)
            rec.file_data = base64.b64encode(content)
            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/onedrive.document/{rec.id}/file_data/{rec.name}?download=true',
                'target': 'self',
            }

    def action_upload_file(self):
        service = self.env['onedrive.service']
        for rec in self:
            if not rec.upload_file or not rec.upload_filename:
                raise UserError(_('Debe seleccionar un archivo para subir.'))
            # Subir al root, puedes cambiar folder_id si lo deseas
            result = service.upload_file('root', rec.upload_filename, base64.b64decode(rec.upload_file))
            # Actualizar datos del documento
            rec.name = result.get('name')
            rec.onedrive_id = result.get('id')
            rec.file_url = result.get('@microsoft.graph.downloadUrl')
            rec.file_size = result.get('size')
            rec.file_type = result.get('file', {}).get('mimeType')
            rec.owner = result.get('createdBy', {}).get('user', {}).get('displayName')
            rec.last_modified = result.get('lastModifiedDateTime')

    @api.model
    def action_sync_onedrive_files(self):
        self.env['onedrive.service'].sync_onedrive_files()
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
