from odoo import models, fields, api

class SaleReport(models.Model):
    _inherit = 'sale.report'

    probability = fields.Float(
        string='Probability (%)',
        readonly=True,
        group_operator='avg',
        widget='percentage',
    )
    margin_percent = fields.Float(
        string='% Margin',
        readonly=True,
        group_operator='avg',
        digits=(4, 2),  # Changed from (5, 2) to (4, 2) - 2 integers and 2 decimals
        widget='percentage'
    )

    def _select_sale(self):
        select_str = super()._select_sale()
        # Use proper SQL syntax to add fields
        select_str += """
            , s.probability as probability
            , s.margin_percent as margin_percent
        """
        return select_str

    def _group_by_sale(self):
        group_by = super()._group_by_sale()
        group_by += ", s.probability, s.margin_percent"
        return group_by
