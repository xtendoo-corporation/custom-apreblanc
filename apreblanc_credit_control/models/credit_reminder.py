# Copyright 2024 Xtendoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ApreblanCreditReminder(models.Model):
    """Historial de recordatorios de crédito enviados al cliente."""

    _name = "apreblanc.credit.reminder"
    _description = "Recordatorio de Crédito Apreblanc"
    _order = "date_sent DESC"
    _rec_name = "date_sent"

    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Cliente",
        required=True,
        ondelete="cascade",
        index=True,
    )
    date_sent = fields.Date(
        string="Fecha de envío",
        required=True,
        default=fields.Date.today,
    )
    overdue_amount = fields.Monetary(
        string="Importe vencido comunicado",
        currency_field="currency_id",
    )
    pending_amount = fields.Monetary(
        string="Importe pendiente comunicado",
        currency_field="currency_id",
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Moneda",
        required=True,
    )
    user_id = fields.Many2one(
        comodel_name="res.users",
        string="Enviado por",
        default=lambda self: self.env.uid,
    )
    notes = fields.Text(string="Notas")

