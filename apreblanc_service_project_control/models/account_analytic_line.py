from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    apreblanc_task_phase = fields.Selection(
        selection=[
            ("preparation", "Preparacion"),
            ("information", "Recogida de informacion"),
            ("analysis", "Analisis"),
            ("report", "Redaccion y entrega de informe"),
        ],
        string="Fase Apreblanc",
        copy=False,
        readonly=True,
    )
    apreblanc_task_stage_name = fields.Char(
        string="Estado tarea",
        copy=False,
        readonly=True,
    )

    def _apreblanc_get_task_from_vals(self, vals):
        task_id = vals.get("task_id") or self.env.context.get("default_task_id")
        if not task_id:
            return False
        task = self.env["project.task"].browse(task_id)
        return task if task.exists() else False

    def _apreblanc_sync_stage_name_with_task_stage(self):
        for line in self.filtered(
            lambda record: record.task_id and record.task_id.project_id.apreblanc_control_enabled
        ):
            stage_name = line.task_id.stage_id.name or _("Sin estado")
            if line.apreblanc_task_stage_name != stage_name:
                super(AccountAnalyticLine, line).write({"apreblanc_task_stage_name": stage_name})

    @api.model
    def _apreblanc_prepare_timesheet_vals(self, vals):
        task = self._apreblanc_get_task_from_vals(vals)
        if not task or not task.project_id.apreblanc_control_enabled:
            return vals

        phase = task.apreblanc_audit_phase
        stage_name = task.stage_id.name or _("Sin estado")

        prepared_vals = dict(vals)
        prepared_vals.setdefault("apreblanc_task_phase", phase)
        prepared_vals["apreblanc_task_stage_name"] = stage_name
        return prepared_vals

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [self._apreblanc_prepare_timesheet_vals(vals) for vals in vals_list]
        lines = super().create(vals_list)
        lines._apreblanc_sync_stage_name_with_task_stage()
        lines._apreblanc_check_project_hours_limit()
        return lines

    def write(self, vals):
        result = super().write(vals)
        self._apreblanc_sync_stage_name_with_task_stage()
        self._apreblanc_check_project_hours_limit()
        return result

    def _apreblanc_check_project_hours_limit(self):
        projects = (self.mapped("project_id") | self.mapped("task_id.project_id")).filtered(
            lambda project: project.apreblanc_control_enabled
            and project.allocated_hours > 0
            and not project.apreblanc_overtime_approved
        )
        for project in projects:
            consumed = sum(project.timesheet_ids.mapped("unit_amount"))
            if consumed > project.allocated_hours:
                raise UserError(
                    _(
                        "El proyecto %(project)s ha superado las horas objetivo (%(target)s). "
                        "Solicita autorización al jefe de proyecto antes de seguir imputando.",
                        project=project.display_name,
                        target=project.allocated_hours,
                    )
                )
