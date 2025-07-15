# -*- coding: utf-8 -*-
import requests
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime

_logger = logging.getLogger(__name__)

class OneDriveService(models.AbstractModel):
    _name = 'onedrive.service'
    _description = 'Servicio de conexión con OneDrive'

    def _get_config(self):
        IrConfig = self.env['ir.config_parameter'].sudo()
        return {
            'client_id': IrConfig.get_param('xtendoo_onedrive_connector.onedrive_client_id'),
            'client_secret': IrConfig.get_param('xtendoo_onedrive_connector.onedrive_client_secret'),
            'tenant_id': IrConfig.get_param('xtendoo_onedrive_connector.onedrive_tenant_id'),
            'redirect_uri': IrConfig.get_param('xtendoo_onedrive_connector.onedrive_redirect_uri'),
            'refresh_token': IrConfig.get_param('xtendoo_onedrive_connector.onedrive_refresh_token'),
        }

    def _get_token(self):
        config = self._get_config()
        if not all([config['client_id'], config['client_secret'], config['tenant_id'], config['refresh_token']]):
            raise UserError(_('Faltan credenciales de OneDrive.'))
        url = f"https://login.microsoftonline.com/{config['tenant_id']}/oauth2/v2.0/token"
        data = {
            'client_id': config['client_id'],
            'client_secret': config['client_secret'],
            'grant_type': 'refresh_token',
            'refresh_token': config['refresh_token'],
            'redirect_uri': config['redirect_uri'],
            'scope': 'https://graph.microsoft.com/.default offline_access',
        }
        resp = requests.post(url, data=data)
        if resp.status_code != 200:
            _logger.error('Error obteniendo token OneDrive: %s', resp.text)
            raise UserError(_('No se pudo obtener el token de acceso de OneDrive.'))
        return resp.json().get('access_token')

    def list_files(self, folder_id=None):
        token = self._get_token()
        headers = {'Authorization': f'Bearer {token}'}
        url = 'https://graph.microsoft.com/v1.0/me/drive/root/children' if not folder_id else f'https://graph.microsoft.com/v1.0/me/drive/items/{folder_id}/children'
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            _logger.error('Error listando archivos OneDrive: %s', resp.text)
            raise UserError(_('No se pudieron listar los archivos de OneDrive.'))
        return resp.json().get('value', [])

    def download_file(self, onedrive_id):
        token = self._get_token()
        headers = {'Authorization': f'Bearer {token}'}
        url = f'https://graph.microsoft.com/v1.0/me/drive/items/{onedrive_id}/content'
        resp = requests.get(url, headers=headers, stream=True)
        if resp.status_code != 200:
            _logger.error('Error descargando archivo OneDrive: %s', resp.text)
            raise UserError(_('No se pudo descargar el archivo de OneDrive.'))
        return resp.content

    def upload_file(self, folder_id, file_name, file_content):
        token = self._get_token()
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/octet-stream',
        }
        url = f'https://graph.microsoft.com/v1.0/me/drive/items/{folder_id}:/{file_name}:/content'
        resp = requests.put(url, headers=headers, data=file_content)
        if resp.status_code not in (200, 201):
            _logger.error('Error subiendo archivo OneDrive: %s', resp.text)
            raise UserError(_('No se pudo subir el archivo a OneDrive.'))
        return resp.json()

    def sync_onedrive_files(self, folder_id=None):
        """
        Sincroniza los archivos de OneDrive con el modelo onedrive.document en Odoo.
        Si folder_id es None, sincroniza la raíz.
        """
        files = self.list_files(folder_id)
        OneDriveDocument = self.env['onedrive.document']
        for file in files:
            if not file.get('file'):
                continue  # Solo archivos, no carpetas
            vals = {
                'name': file.get('name'),
                'onedrive_id': file.get('id'),
                'file_url': file.get('@microsoft.graph.downloadUrl'),
                'file_size': file.get('size'),
                'file_type': file.get('file', {}).get('mimeType'),
                'owner': file.get('createdBy', {}).get('user', {}).get('displayName'),
                'last_modified': file.get('lastModifiedDateTime'),
            }
            doc = OneDriveDocument.search([('onedrive_id', '=', file.get('id'))], limit=1)
            if doc:
                doc.write(vals)
            else:
                OneDriveDocument.create(vals)
