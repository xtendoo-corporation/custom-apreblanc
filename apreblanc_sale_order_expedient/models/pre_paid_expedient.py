from odoo import api, fields, models, _


class PrePaidExpedient(models.Model):
    _name = "pre.paid.expedient"
    _description = "Pre-paid Expedient"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(
        string="Name",
        required=True,
        default=lambda self: _("New Pre-paid Expedient"),
        tracking=True,
    )

    partner_id = fields.Many2one(
        "res.partner", string="Customer", required=True, tracking=True
    )

    client_id = fields.Char(
        string="Client ID", required=True, copy=False, index=True, tracking=True
    )

    expedient_number = fields.Char(
        string="Expedient Number", required=True, copy=False, index=True, tracking=True
    )

    initial_balance = fields.Float(string="Initial Balance", default=0.0, tracking=True)

    current_balance = fields.Float(string="Current Balance", default=0.0, tracking=True)

    date_created = fields.Date(
        string="Date Created", default=fields.Date.today, required=True, tracking=True
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("active", "Active"),
            ("suspended", "Suspended"),
            ("closed", "Closed"),
        ],
        string="State",
        default="draft",
        tracking=True,
    )

    notes = fields.Text(string="Notes")

    _sql_constraints = [
        (
            "client_expedient_unique",
            "unique(client_id, expedient_number)",
            "The combination of Client ID and Expedient Number must be unique!",
        )
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New Pre-paid Expedient")) == _(
                "New Pre-paid Expedient"
            ):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "pre.paid.expedient"
                ) or _("New Pre-paid Expedient")
        return super().create(vals_list)
