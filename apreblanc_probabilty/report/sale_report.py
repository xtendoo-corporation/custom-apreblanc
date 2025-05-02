from odoo import models, fields

class SaleReport(models.Model):
    _inherit = 'sale.report'

    probability = fields.Float(
        string='Probability',
        readonly=True,
        group_operator='avg',
        widget='percentage',
    )
    # margin_percent = fields.Float(
    #     string='% Margen',
    #     readonly=True,
    #     group_operator='avg',
    #     digits=(5, 2),
    #     widget='percentage',
    # )

    def _select_sale(self):
        select_str = super()._select_sale()
        select_str += """
            , s.probability AS probability
        """
        # La parte del margin_percent se mantiene comentada
        return select_str

    def _group_by_sale(self):
        group_by = super()._group_by_sale()
        # Hay que agrupar por s.probability, y no por margin_percent
        group_by += ", s.probability"
        return group_by
