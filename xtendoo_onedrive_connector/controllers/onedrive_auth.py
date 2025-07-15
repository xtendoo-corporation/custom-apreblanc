from odoo import http
from odoo.http import request
import logging
_logger = logging.getLogger(__name__)

class OneDriveAuthController(http.Controller):
    @http.route('/onedrive/callback', type='http', auth='public', csrf=False)
    def onedrive_callback(self, **kwargs):
        code = kwargs.get('code')
        state = kwargs.get('state')
        error = kwargs.get('error')
        _logger.warning(f"[OneDrive] Callback recibido. code={code}, state={state}, error={error}")
        if code:
            return request.render('xtendoo_onedrive_connector.onedrive_callback_template', {'code': code, 'state': state})
        elif error:
            return f"Error: {error}"
        else:
            return "No se recibió ningún código de autorización."
