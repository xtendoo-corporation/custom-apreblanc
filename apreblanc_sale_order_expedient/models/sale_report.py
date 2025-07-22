from odoo import models, fields

class SaleReport(models.Model):
    _inherit = 'sale.report'

    margin_percent = fields.Float(
        string='Margin %',
        group_operator="avg",
        widget='percentage'  # Ahora este parámetro será válido
    )

    def _valid_field_parameter(self, field, name):
        """Permitir el parámetro widget para los campos del modelo"""
        return name == 'widget' or super()._valid_field_parameter(field, name)
