# Copyright 2024 Xtendoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class CreditReminderHistory(models.Model):
    """Historial de recordatorios de crédito enviados al cliente."""

    _name = "credit.reminder.history"
    _description = "Historial Recordatorio de Crédito"
    _order = "date_sent DESC"
    _rec_name = "date_sent"

    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Cliente",
        required=True,
        ondelete="cascade",
        index=True,
    )
    date_sent = fields.Datetime(
        string="Fecha de envío",
        required=True,
        default=fields.Datetime.now,
    )
    overdue_amount = fields.Monetary(
        string="Importe vencido",
        currency_field="currency_id",
    )
    pending_amount = fields.Monetary(
        string="Importe pendiente",
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
    subject = fields.Char(string="Asunto")
    body = fields.Html(string="Cuerpo del mensaje")
    email_to = fields.Char(string="Destinatario")
    state = fields.Selection(
        selection=[
            ("sent", "Enviado"),
            ("failed", "Fallido"),
        ],
        string="Estado",
        default="sent",
    )
    email_sent = fields.Boolean(
        string="Email enviado",
        default=True,
    )
    notes = fields.Text(string="Notas")
