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
APREBLANC_PENDING_STAGE_NAME = "Pendiente de asignar"
APREBLANC_DONE_STAGE_NAME = "Informe"


class ProjectTask(models.Model):
    _inherit = "project.task"

    apreblanc_start_date = fields.Date(
        string="Fecha inicio",
        copy=False,
    )
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

    def _apreblanc_check_start_dependency(self, new_stage_id):
        self.ensure_one()
        if not self.project_id.apreblanc_control_enabled or not self.apreblanc_sale_line_id:
            return

        new_stage = self.env["project.task.type"].browse(new_stage_id)
        if (
            not self.stage_id
            or not new_stage.exists()
            or self.stage_id.name != APREBLANC_PENDING_STAGE_NAME
            or new_stage.name == APREBLANC_PENDING_STAGE_NAME
            or not self.depend_on_ids
        ):
            if (
                self.stage_id
                and new_stage.exists()
                and self.stage_id.name == APREBLANC_PENDING_STAGE_NAME
                and new_stage.name != APREBLANC_PENDING_STAGE_NAME
            ):
                today = fields.Date.context_today(self)
                if self.apreblanc_start_date and self.apreblanc_start_date > today:
                    raise UserError(
                        _(
                            "No puedes iniciar esta tarea antes de su fecha de inicio (%(date)s).",
                            date=self.apreblanc_start_date,
                        )
                    )
            return

        blocking_tasks = self.depend_on_ids.filtered(
            lambda task: task.stage_id.name != APREBLANC_DONE_STAGE_NAME
        )
        if blocking_tasks:
            raise UserError(
                _(
                    "No puedes iniciar esta tarea hasta finalizar la anterior en etapa 'Informe'. "
                    "Tareas pendientes: %(tasks)s",
                    tasks=", ".join(blocking_tasks.mapped("display_name")),
                )
            )
        today = fields.Date.context_today(self)
        if self.apreblanc_start_date and self.apreblanc_start_date > today:
            raise UserError(
                _(
                    "No puedes iniciar esta tarea antes de su fecha de inicio (%(date)s).",
                    date=self.apreblanc_start_date,
                )
            )

    def _apreblanc_sync_timesheet_stage_name(self):
        for task in self.filtered(
            lambda record: record.project_id.apreblanc_control_enabled and record.apreblanc_sale_line_id
        ):
            stage_name = task.stage_id.name or _("Sin estado")
            task.timesheet_ids.write({"apreblanc_task_stage_name": stage_name})

    def write(self, vals):
        sync_timesheet_stage_name = "stage_id" in vals and vals["stage_id"]
        if "stage_id" in vals and vals["stage_id"]:
            for task in self:
                task._apreblanc_check_start_dependency(vals["stage_id"])
        if "apreblanc_audit_phase" in vals:
            for task in self:
                task._apreblanc_check_phase_transition(vals["apreblanc_audit_phase"])
        result = super().write(vals)
        if sync_timesheet_stage_name:
            self._apreblanc_sync_timesheet_stage_name()
        return result
