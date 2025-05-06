from odoo import models, fields

class SaleReport(models.Model):
    _inherit = 'sale.report'

    probability = fields.Float(
        string='% Probability',
        readonly=True,
        group_operator='avg',
        widget='percentage',
    )
    margin_percent = fields.Float(
        string='% Margin',
        readonly=True,
        group_operator='avg',
        digits=(5, 2),
        widget='percentage'
    )

    def _select_sale(self):
        select_str = super()._select_sale()
        select_str += """
            , s.probability AS probability
            , s.margin_percent AS margin_percent
        """
        return select_str

    def _group_by_sale(self):
        group_by = super()._group_by_sale()
        group_by += ", s.probability, s.margin_percent"
        return group_by
