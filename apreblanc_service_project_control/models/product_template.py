from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    apreblanc_create_service_project = fields.Boolean(
        string="Crear proyecto operativo",
        help="Si está marcado, las líneas de este servicio generan el proyecto "
        "operativo de Apreblanc al confirmar el pedido.",
    )
    apreblanc_target_hours = fields.Float(
        string="Horas objetivo servicio",
        help="Horas objetivo por unidad vendida para control de rentabilidad.",
    )
