from odoo import _, api, fields, models
from odoo.exceptions import UserError


APREBLANC_AUDIT_PHASE_SELECTION = [
    ("preparation", "Preparacion"),
    ("information", "Recogida de informacion"),
    ("analysis", "Analisis"),
    ("report", "Redaccion y entrega de informe"),
]

APREBLANC_AUDIT_PHASE_SEQUENCE = {
    phase: index for index, (phase, _label) in enumerate(APREBLANC_AUDIT_PHASE_SELECTION)
}


class ProjectTask(models.Model):
    _inherit = "project.task"

    apreblanc_audit_phase = fields.Selection(
        APREBLANC_AUDIT_PHASE_SELECTION,
        string="Fase de auditoria",
        default="preparation",
        required=True,
        tracking=True,
    )

    apreblanc_sale_line_id = fields.Many2one(
        "sale.order.line",
        string="Línea de venta origen",
        copy=False,
        index=True,
        readonly=True,
    )

    def _get_apreblanc_audit_phase_label(self, phase=None):
        selection = dict(self._fields["apreblanc_audit_phase"].selection)
        phase_key = phase or self.apreblanc_audit_phase
        return selection.get(phase_key, _("Sin fase"))

    def _apreblanc_check_phase_transition(self, new_phase):
        self.ensure_one()
        if not self.project_id.apreblanc_control_enabled or not new_phase:
            return

        current_index = APREBLANC_AUDIT_PHASE_SEQUENCE.get(self.apreblanc_audit_phase, 0)
        new_index = APREBLANC_AUDIT_PHASE_SEQUENCE.get(new_phase, 0)
        if new_index == current_index:
            return
        if new_index < current_index:
            raise UserError(
                _(
                    "La tarea %(task)s no puede retroceder de la fase %(current)s a %(new)s.",
                    task=self.display_name,
                    current=self._get_apreblanc_audit_phase_label(),
                    new=self._get_apreblanc_audit_phase_label(new_phase),
                )
            )
        if new_index > current_index + 1:
            raise UserError(
                _(
                    "La tarea %(task)s debe avanzar fase a fase. No se puede saltar de %(current)s a %(new)s.",
                    task=self.display_name,
                    current=self._get_apreblanc_audit_phase_label(),
                    new=self._get_apreblanc_audit_phase_label(new_phase),
                )
            )

    def write(self, vals):
        if "apreblanc_audit_phase" in vals:
            for task in self:
                task._apreblanc_check_phase_transition(vals["apreblanc_audit_phase"])
        return super().write(vals)
