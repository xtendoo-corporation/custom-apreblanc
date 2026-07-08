from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    apreblanc_target_hours = fields.Float(
        string="Horas objetivo servicio",
        help="Horas objetivo por unidad vendida para control de rentabilidad.",
    )
