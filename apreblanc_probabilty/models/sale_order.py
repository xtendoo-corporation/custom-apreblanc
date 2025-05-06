from odoo import api, fields, models

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    probability = fields.Float(
        string='% Probability',
        default=0.0,
        help='Probability of closing the sale order',
    )
