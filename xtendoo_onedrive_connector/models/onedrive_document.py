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
        # Obtener la configuración de OneDrive
        settings = self.env['onedrive.settings'].search([], limit=1)
        if not settings or not settings.onedrive_refresh_token:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'type': 'danger',
                    'message': 'No hay configuración de OneDrive o falta el refresh token.',
                    'sticky': False,
                }
            }

        # Paso 1: Obtener access_token
        token_url = f"https://login.microsoftonline.com/{settings.onedrive_tenant_id}/oauth2/v2.0/token"
        data = {
            'client_id': settings.onedrive_client_id,
            'client_secret': settings.onedrive_client_secret,
            'grant_type': 'refresh_token',
            'refresh_token': settings.onedrive_refresh_token,
            'scope': 'offline_access Files.ReadWrite.All User.Read',
        }
        token_response = requests.post(token_url, data=data)
        if token_response.status_code != 200:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'type': 'danger',
                    'message': 'No se pudo obtener el access token de OneDrive.',
                    'sticky': False,
                }
            }
        access_token = token_response.json().get('access_token')
        if not access_token:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'type': 'danger',
                    'message': 'No se recibió access token de OneDrive.',
                    'sticky': False,
                }
            }

        headers = {'Authorization': f'Bearer {access_token}'}

        def sync_folder(parent_id, parent_odoo_id=None):
            url = f"https://graph.microsoft.com/v1.0/me/drive/items/{parent_id}/children" if parent_id else "https://graph.microsoft.com/v1.0/me/drive/root/children"
            response = requests.get(url, headers=headers)
            if response.status_code != 200:
                return
            for item in response.json().get('value', []):
                vals = {
                    'name': item.get('name'),
                    'onedrive_id': item.get('id'),
                    'file_url': item.get('@microsoft.graph.downloadUrl'),
                    'file_size': item.get('size'),
                    'file_type': item.get('file', {}).get('mimeType') if item.get('file') else None,
                    'owner': item.get('createdBy', {}).get('user', {}).get('displayName'),
                    'last_modified': item.get('lastModifiedDateTime'),
                    'parent_id': parent_odoo_id.id if parent_odoo_id else False,
                    'is_folder': item.get('folder') is not None,
                }
                doc = self.env['onedrive.document'].search([('onedrive_id', '=', item.get('id'))], limit=1)
                if doc:
                    doc.write(vals)
                else:
                    doc = self.env['onedrive.document'].create(vals)
                if item.get('folder'):
                    sync_folder(item.get('id'), doc)

        # Sincronizar desde la raíz
        sync_folder(None)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Sincronización',
                'type': 'success',
                'message': 'Sincronización de OneDrive finalizada.',
                'sticky': False,
            }
        }

    def action_download_file(self):
        # Lógica para descargar un archivo desde OneDrive
        return True

    def action_upload_file(self):
        # Lógica para subir un archivo a OneDrive
        return True
