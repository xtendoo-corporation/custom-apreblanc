from odoo import api, fields, models

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    probability = fields.Float(
        string='Probability (%)',
        default=0.0,
        help='Probability of closing the sale order',
    )

    margin_percent = fields.Float(
        string='% Margin',
        compute='_compute_margin_percent',
        store=True,
        digits=(5, 2),
    )

    @api.depends('margin', 'amount_untaxed')
    def _compute_margin_percent(self):
        for order in self:
            order.margin_percent = order.amount_untaxed and (order.margin / order.amount_untaxed) * 100 or 0.0
