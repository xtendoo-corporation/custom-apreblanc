# Copyright 2024 Xtendoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    credit_control_debt_limit = fields.Monetary(
        string="Límite de deuda vencida",
        currency_field="currency_id",
        default=0.0,
        help="Importe mínimo de deuda vencida (en moneda de la empresa) a partir del cual "
        "un cliente aparece en el análisis de control de crédito.",
    )


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    credit_control_debt_limit = fields.Monetary(
        related="company_id.credit_control_debt_limit",
        currency_field="currency_id",
        readonly=False,
        string="Límite de deuda vencida",
    )

