from odoo import api, fields, models

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    probability = fields.Float(
        string='Probabilidad',
        default=0.0,
        help='Probabilidad de confirmación del pedido',
    )
# Añadir este campo al modelo SaleOrder en models/sale_order.py
    margin_percent = fields.Float(
        string='% Margen',
        compute='_compute_margin_percent',
        store=True,
        digits=(5, 2),
        help='Porcentaje de margen del pedido',
    )

    @api.depends('amount_untaxed', 'margin')
    def _compute_margin_percent(self):
        for order in self:
            if order.amount_untaxed != 0:
                order.margin_percent = (order.margin / order.amount_untaxed) * 100
            else:
                order.margin_percent = 0.0
