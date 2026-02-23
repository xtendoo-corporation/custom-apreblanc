# Copyright 2024 Xtendoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    credit_reminder_ids = fields.One2many(
        comodel_name="apreblanc.credit.reminder",
        inverse_name="partner_id",
        string="Recordatorios de crédito",
    )
    credit_reminder_count = fields.Integer(
        compute="_compute_credit_reminder_count",
        string="Nº Recordatorios",
    )

    def _compute_credit_reminder_count(self):
        for partner in self:
            partner.credit_reminder_count = len(partner.credit_reminder_ids)

    def action_view_credit_reminders(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Recordatorios de crédito"),
            "res_model": "apreblanc.credit.reminder",
            "view_mode": "tree,form",
            "domain": [("partner_id", "=", self.id)],
            "context": {"default_partner_id": self.id},
        }

