from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    apreblanc_target_hours = fields.Float(
        string="Horas objetivo",
        compute="_compute_apreblanc_target_hours",
        store=True,
        readonly=True,
    )

    @api.depends("product_uom_qty", "product_template_id.apreblanc_target_hours")
    def _compute_apreblanc_target_hours(self):
        for line in self:
            if line.display_type or line.product_template_id.detailed_type != "service":
                line.apreblanc_target_hours = 0.0
                continue
            line.apreblanc_target_hours = (
                line.product_uom_qty * line.product_template_id.apreblanc_target_hours
            )
