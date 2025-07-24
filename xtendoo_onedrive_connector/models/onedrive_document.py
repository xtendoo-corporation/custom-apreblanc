from odoo import models, fields, api
import requests

class OneDriveDocument(models.Model):
    _name = 'onedrive.document'
    _description = 'OneDrive Document'

    name = fields.Char(string='Name', required=True)
    onedrive_id = fields.Char(string='OneDrive ID')
    file_url = fields.Char(string='File URL')
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
        Usa el servicio mejorado de OneDrive y refresca la vista después
        """
        try:
            # Usar el servicio mejorado de OneDrive
            service = self.env['onedrive.service']
            result = service.sync_onedrive_files()

            if result['success']:
                # Después de una sincronización exitosa, retornar directamente a la vista actualizada
                return {
                    'type': 'ir.actions.act_window',
                    'name': 'Documentos OneDrive - Sincronizado',
                    'res_model': 'onedrive.document',
                    'view_mode': 'tree,form',
                    'target': 'current',
                    'context': {
                        'search_default_group_by_parent': 1,
                        'default_message': result['message']
                    }
                }
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Error de Sincronización',
                        'type': 'danger',
                        'message': result['message'],
                        'sticky': True,
                    }
                }

        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error Inesperado',
                    'type': 'danger',
                    'message': f'Error durante la sincronización: {str(e)}',
                    'sticky': True,
                }
            }

    def action_download_file(self):
        # Lógica para descargar un archivo desde OneDrive
        return True

    def action_upload_file(self):
        # Lógica para subir un archivo a OneDrive
        return True
