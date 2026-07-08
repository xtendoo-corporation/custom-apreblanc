from odoo import fields, models


class ProjectTask(models.Model):
    _inherit = "project.task"

    apreblanc_sale_line_id = fields.Many2one(
        "sale.order.line",
        string="Línea de venta origen",
        copy=False,
        index=True,
        readonly=True,
    )
