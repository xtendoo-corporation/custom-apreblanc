from odoo import http
from odoo.http import request
import base64

class OneDriveDocumentController(http.Controller):

    @http.route('/onedrive/pdf/<int:document_id>', type='http', auth='user', methods=['GET'])
    def serve_pdf(self, document_id, **kwargs):
        """Servir PDF para previsualización"""
        try:
            document = request.env['onedrive.document'].browse(document_id)
            if not document.exists() or not document.file_data:
                return request.not_found()

            # Decodificar el archivo PDF
            file_content = base64.b64decode(document.file_data)

            # Devolver el PDF con headers correctos
            return request.make_response(
                file_content,
                headers=[
                    ('Content-Type', 'application/pdf'),
                    ('Content-Disposition', f'inline; filename="{document.name}"'),
                    ('Cache-Control', 'max-age=3600'),
                ]
            )
        except Exception:
            return request.not_found()
