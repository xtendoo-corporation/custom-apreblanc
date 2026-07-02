from odoo import models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _track_subtype(self, init_values):
        self.ensure_one()
        economic_fields = {"amount_total", "amount_tax", "amount_untaxed"}
        if economic_fields & set(init_values.keys()):
            return self.env.ref("apreblanc_chatter_filter.mt_economic_change")
        return super()._track_subtype(init_values)
