from odoo import http
from odoo.http import request
import logging
_logger = logging.getLogger(__name__)

class OneDriveAuthController(http.Controller):
    @http.route('/onedrive/callback', type='http', auth='user')
    def onedrive_callback(self, **kwargs):
        code = kwargs.get('code')
        state = kwargs.get('state')
        error = kwargs.get('error')
        _logger.warning(f"[OneDrive] Callback recibido. code={code}, state={state}, error={error}")

        if error:
            return request.render('xtendoo_onedrive_connector.onedrive_callback_error', {
                'error': error
            })

        if not code:
            return request.render('xtendoo_onedrive_connector.onedrive_callback_error', {
                'error': 'No se recibió ningún código de autorización'
            })

        # Buscar la configuración de OneDrive
        settings = request.env['onedrive.settings'].sudo().search([], limit=1)
        if not settings:
            return request.render('xtendoo_onedrive_connector.onedrive_callback_error', {
                'error': 'No hay configuración de OneDrive'
            })

        # Guardar el token de refresco
        success = settings.sudo().save_refresh_token(code)
        if not success:
            return request.render('xtendoo_onedrive_connector.onedrive_callback_error', {
                'error': 'Error al obtener el token de refresco'
            })

        # Redireccionar a la vista de documentos de OneDrive
        return request.redirect('/web#action=onedrive_document_action')

    @http.route('/onedrive/view', type='http', auth='user')
    def onedrive_view(self, **kwargs):
        # Simplemente redirecciona a la acción del cliente
        return request.redirect('/web#action=onedrive_document_action')
