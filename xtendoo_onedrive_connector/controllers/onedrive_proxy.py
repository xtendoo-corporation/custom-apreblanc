from odoo import http
from odoo.http import request
import requests
import base64
import mimetypes

class OneDriveProxyController(http.Controller):

    @http.route('/onedrive/preview/<int:document_id>', type='http', auth='user', methods=['GET'])
    def preview_document(self, document_id, **kwargs):
        """Endpoint para servir archivos de OneDrive como proxy"""
        try:
            document = request.env['onedrive.document'].browse(document_id)
            if not document.exists() or not document.file_url:
                return request.not_found()

            # Si el archivo está almacenado localmente en file_data, usarlo
            if document.file_data:
                file_content = base64.b64decode(document.file_data)
                filename = document.name or 'document'

                # Detectar tipo MIME
                content_type = mimetypes.guess_type(filename)[0]
                if not content_type:
                    content_type = 'application/octet-stream'

                return request.make_response(
                    file_content,
                    headers=[
                        ('Content-Type', content_type),
                        ('Content-Disposition', f'inline; filename="{filename}"'),
                        ('Cache-Control', 'max-age=3600'),
                    ]
                )

            # Si no está almacenado localmente, intentar descargar de OneDrive
            elif document.file_url:
                # Para archivos de imagen, intentar proxy
                if document.file_type and any(ext in document.file_type.lower() for ext in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg']):
                    try:
                        response = requests.get(document.file_url, timeout=30)
                        if response.status_code == 200:
                            content_type = response.headers.get('content-type', 'image/jpeg')
                            return request.make_response(
                                response.content,
                                headers=[
                                    ('Content-Type', content_type),
                                    ('Content-Disposition', f'inline; filename="{document.name}"'),
                                    ('Cache-Control', 'max-age=3600'),
                                ]
                            )
                    except Exception:
                        pass

                # Para otros archivos, redirigir a OneDrive
                return request.redirect(document.file_url)

            return request.not_found()

        except Exception as e:
            return request.not_found()

    @http.route('/onedrive/download/<int:document_id>', type='http', auth='user', methods=['GET'])
    def download_document(self, document_id, **kwargs):
        """Endpoint para descargar archivos de OneDrive"""
        try:
            document = request.env['onedrive.document'].browse(document_id)
            if not document.exists():
                return request.not_found()

            if document.file_data:
                file_content = base64.b64decode(document.file_data)
                filename = document.name or 'document'

                content_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'

                return request.make_response(
                    file_content,
                    headers=[
                        ('Content-Type', content_type),
                        ('Content-Disposition', f'attachment; filename="{filename}"'),
                    ]
                )
            elif document.file_url:
                return request.redirect(document.file_url)

            return request.not_found()

        except Exception:
            return request.not_found()
