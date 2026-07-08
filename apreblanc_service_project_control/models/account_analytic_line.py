from odoo import _, api, models
from odoo.exceptions import UserError


class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._apreblanc_check_project_hours_limit()
        return lines

    def write(self, vals):
        result = super().write(vals)
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
