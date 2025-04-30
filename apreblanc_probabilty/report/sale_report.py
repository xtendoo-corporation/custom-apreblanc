from odoo import models, fields, api

class SaleReport(models.Model):
    _inherit = 'sale.report'

    probability = fields.Float(string='Probability', readonly=True)

    def _select_sale(self):
        select = super(SaleReport, self)._select_sale()
        select += ", s.probability AS probability"
        return select

    def _group_by_sale(self):
        group_by = super(SaleReport, self)._group_by_sale()
        group_by += ", s.probability"
        return group_by

    # def _query(self):
    #     with_ = self._with_sale()
    #     query = f"""
    #         {"WITH" + with_ + "(" if with_ else ""}
    #         SELECT {self._select_sale()}
    #         FROM {self._from_sale()}
    #         WHERE {self._where_sale()}
    #         GROUP BY {self._group_by_sale()}
    #         {")" if with_ else ""}
    #     """
    #     return query
