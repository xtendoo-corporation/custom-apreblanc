# -*- coding: utf-8 -*-
# Controlador para exponer la ruta /import_expedient/excel que usa la vista tipo `banner_route`.
from odoo import http
from odoo.http import request


class ImportExpedientController(http.Controller):
    @http.route('/import_expedient/excel', type='json', auth='user')
    def import_expedient_excel(self, **kwargs):
        """Devuelve el HTML para el banner usado en la vista (banner_route).

        El frontend espera una respuesta JSON con la clave 'html'. Se intenta
        renderizar una plantilla qweb llamada 'sale_order_expedient.import_expedient_banner'
        si existe; si no, se devuelve un HTML mínimo inline.
        """
        # Protecciones básicas: si hay contexto pasado, actualizarlo
        context = kwargs.get('context')
        if context:
            request.update_context(**context)

        # Intentar renderizar una plantilla QWeb específica del módulo
        try:
            html = request.env['ir.qweb']._render(
                'sale_order_expedient.import_expedient_banner', {})
            return {'html': html}
        except Exception:
            # Si la plantilla no existe o falla, devolver un HTML sencillo
            fallback = (
                '<div class="o_onboarding_banner o_import_expedient_banner">'
                '<div class="o_banner_content">'
                '<h4>Importar Expedientes desde Excel</h4>'
                '<p>Utilice el asistente para importar expedientes en masa. '
                '<a href="#" data-action="open_import_expedient_wizard">Abrir asistente</a></p>'
                '</div></div>'
            )
            return {'html': fallback}
# Package initializer for controllers of sale_order_expedient
from . import main

