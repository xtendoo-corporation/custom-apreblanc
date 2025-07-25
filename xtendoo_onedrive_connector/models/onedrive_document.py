from odoo import models, fields, api
import requests

class OneDriveDocument(models.Model):
    _name = 'onedrive.document'
    _description = 'OneDrive Document'

    name = fields.Char(string='Name', required=True)
    onedrive_id = fields.Char(string='OneDrive ID')
    file_url = fields.Char(string='File URL')
    preview_url = fields.Char(string='Preview URL', compute='_compute_preview_url')
    file_size = fields.Integer(string='File Size')
    file_type = fields.Char(string='File Type')
    owner = fields.Char(string='Owner')
    last_modified = fields.Datetime(string='Last Modified')
    parent_id = fields.Many2one('onedrive.document', string='Parent Folder')
    is_folder = fields.Boolean(string='Is Folder', default=False)
    file_data = fields.Binary(string='File Data')
    upload_file = fields.Binary(string='Upload File')
    upload_filename = fields.Char(string='Upload Filename')

    @api.model
    def action_sync_onedrive(self):
        """
        Método llamado desde la interfaz para sincronizar con OneDrive
        """
        try:
            # Usar el servicio mejorado de OneDrivee
            service = self.env['onedrive.service']
            result = service.sync_onedrive_files()

            # Mostrar notificación y recargar la vista
            if result['success']:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'reload',
                    'params': {
                        'title': 'Sincronización Exitosa',
                        'type': 'success',
                        'message': result['message'],
                        'sticky': False,
                    }
                }
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'reload',
                    'params': {
                        'title': 'Error en la Sincronización',
                        'type': 'danger',
                        'message': result['error'],
                        'sticky': False,
                    }
                }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'reload',
                'params': {
                    'title': 'Error en la Sincronización',
                    'type': 'danger',
                    'message': str(e),
                    'sticky': False,
                }
            }

    def action_download_file(self):
        # Lógica para descargar un archivo desde OneDriveaa
        return True

    def action_upload_file(self):
        # Lógica para subir un archivo a OneDrive
        return True

    @api.depends('file_url')
    def _compute_preview_url(self):
        for record in self:
            if record.file_url and not record.is_folder:
                # Convertir URL de OneDrive a URL de previsualización
                if 'sharepoint.com' in record.file_url or 'onedrive.live.com' in record.file_url:
                    # Para URLs de OneDrive, intentar convertir a URL de previsualización
                    if '?download=1' in record.file_url:
                        # Reemplazar download=1 con embed=1 para previsualización
                        record.preview_url = record.file_url.replace('?download=1', '?embed=1')
                    elif 'view.aspx' in record.file_url:
                        # Para URLs de SharePoint, agregar parámetros de embed
                        record.preview_url = record.file_url + '&action=embedview'
                    else:
                        record.preview_url = record.file_url
                else:
                    record.preview_url = record.file_url
            else:
                record.preview_url = False
