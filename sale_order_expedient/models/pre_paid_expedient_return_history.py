from odoo import api, fields, models


class PrePaidExpedientReturnHistory(models.Model):
    _name = "pre.paid.expedient.return.history"
    _description = "Historial de devoluciones de expedientes prepagados"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "return_date desc"

    name = fields.Char("Referencia", compute="_compute_name", store=True)
    pre_paid_expedient_id = fields.Many2one(
        "pre.paid.expedient",
        string="Expediente Prepagado",
        required=True,
        ondelete="cascade"
    )
    return_date = fields.Datetime(
        "Fecha de Devolución",
        default=fields.Datetime.now,
        required=True
    )
    return_reason_id = fields.Many2one(
        "expedient.return.reason",
        string="Motivo de Devolución",
        required=True
    )
    notes = fields.Text("Notas")
    user_id = fields.Many2one(
        "res.users",
        string="Usuario",
        default=lambda self: self.env.user,
        required=True
    )

    @api.depends("pre_paid_expedient_id", "return_date")
    def _compute_name(self):
        for record in self:
            if record.pre_paid_expedient_id and record.return_date:
                record.name = f"{record.pre_paid_expedient_id.name} - {record.return_date}"
            else:
                record.name = "Nueva devolución"

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)

        # Cambiar el estado de los expedientes a "pendiente de documentación"
        for record in records:
            if record.pre_paid_expedient_id:
                record.pre_paid_expedient_id.write({
                    'expedient_state': 'pendiente_documentacion'
                })
                # Añadir mensaje en el chatter del expediente
                record.pre_paid_expedient_id.message_post(
                    body=f"Estado cambiado a 'Pendiente de Documentación' debido a la devolución creada el {record.return_date}",
                    subtype_xmlid='mail.mt_note'
                )

        return records
