from odoo import models, fields, api
from odoo.exceptions import ValidationError
import urllib.parse

class OneDriveSettings(models.Model):
    _name = 'onedrive.settings'
    _description = 'Configuración de OneDrive'
    _rec_name = 'onedrive_client_id'

    onedrive_client_id = fields.Char('Client ID', required=True)
    onedrive_client_secret = fields.Char('Client Secret', required=True)
    onedrive_tenant_id = fields.Char('Tenant ID', required=True)
    onedrive_redirect_uri = fields.Char('Redirect URI', required=True)
    onedrive_refresh_token = fields.Char('Refresh Token')
    onedrive_sync_folder = fields.Char('ID de Carpeta a Sincronizar', help='ID de la carpeta de OneDrive que quieres sincronizar. Déjalo en blanco para sincronizar la carpeta raíz.')
    onedrive_sync_folder_name = fields.Char('Nombre de Carpeta', help='Nombre legible de la carpeta de OneDrive configurada para sincronización.', readonly=True)

    onedrive_max_depth = fields.Integer(
        'Profundidad máxima', default=5,
        help='Niveles de subcarpetas que explora la sincronización (1-20). '
             'Más niveles = sincronización más larga.')

    attachment_sync_enabled = fields.Boolean(
        'Subir adjuntos del chatter a OneDrive', default=False,
        help='Si está activo, los adjuntos de los modelos indicados se copian a OneDrive '
             'en segundo plano. Odoo conserva siempre el archivo original.')
    attachment_sync_models = fields.Char(
        'Modelos a sincronizar', default='sale.order,account.move,account.payment,purchase.order,stock.picking',
        help='Nombres técnicos de modelo separados por comas (por ejemplo: sale.order,account.move).')
    attachment_sync_max_mb = fields.Integer(
        'Tamaño máximo por adjunto (MB)', default=50,
        help='Los adjuntos mayores se omiten (consumen memoria al subirse).')

    def _get_attachment_sync_models(self):
        self.ensure_one()
        models_ = {m.strip() for m in (self.attachment_sync_models or '').split(',') if m.strip()}
        return {m for m in models_ if m in self.env.registry}  # ignora nombres que no existen

    def action_process_attachment_sync(self):
        """Procesa ahora la cola de adjuntos pendientes (sin esperar al cron)."""
        stats = self.env['onedrive.attachment.sync']._cron_process_pending()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Adjuntos OneDrive',
                'message': 'Procesados: %(processed)s · subidos: %(done)s · con error: %(failed)s' % stats,
                'type': 'success' if not stats['failed'] else 'warning',
            },
        }

    @api.constrains('onedrive_max_depth')
    def _check_onedrive_max_depth(self):
        for rec in self:
            if not 1 <= rec.onedrive_max_depth <= 20:
                raise ValidationError('La profundidad máxima debe estar entre 1 y 20.')

    def get_auth_url(self):
        # Usar tenant específico en lugar del endpoint común
        if not (self.onedrive_client_id and self.onedrive_redirect_uri and self.onedrive_tenant_id):
            return False

        base_url = f"https://login.microsoftonline.com/{self.onedrive_tenant_id}/oauth2/v2.0/authorize"

        # Definir scopes para OneDrive Personal y Business (más compatible)
        scopes = "openid offline_access Files.ReadWrite.All"
        encoded_scopes = urllib.parse.quote(scopes)
        encoded_redirect_uri = urllib.parse.quote(self.onedrive_redirect_uri)

        params = (
            f"client_id={self.onedrive_client_id}"
            f"&response_type=code"
            f"&redirect_uri={encoded_redirect_uri}"
            f"&response_mode=query"
            f"&scope={encoded_scopes}"
            f"&state=odoo_onedrive"
        )
        return base_url + "?" + params

    def action_get_onedrive_auth_url(self):
        url = self.get_auth_url()
        if url:
            return {
                'type': 'ir.actions.act_url',
                'url': url,
                'target': 'new',
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Faltan datos',
                    'message': 'Debes rellenar Client ID, Tenant ID y Redirect URI.',
                    'type': 'warning',
                }
            }
