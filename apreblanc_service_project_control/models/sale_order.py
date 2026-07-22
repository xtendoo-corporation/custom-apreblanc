from odoo import _, api, fields, models
from odoo.exceptions import UserError

APREBLANC_PROJECT_STAGES = [
    ("Pendiente de asignar", 10, False),
    ("Trabajo previo", 20, False),
    ("Recogida de información", 30, False),
    ("Análisis de información", 40, False),
    ("Informe", 50, True),
]


class SaleOrder(models.Model):
    _inherit = "sale.order"

    apreblanc_service_type = fields.Selection(
        [
            ("audit", "Auditoría"),
            ("consulting", "Consultoría"),
            ("training", "Formación"),
        ],
        string="Tipo de servicio",
        help="Tipo de servicio que se prestará",
        required=True,
    )
    apreblanc_service_project_id = fields.Many2one(
        "project.project",
        string="Proyecto operativo",
        copy=False,
        readonly=True,
    )
    apreblanc_hours_target = fields.Float(
        string="Horas presupuestadas",
        compute="_compute_apreblanc_service_metrics",
    )
    apreblanc_hours_consumed = fields.Float(
        string="Horas consumidas",
        compute="_compute_apreblanc_service_metrics",
    )
    apreblanc_hours_remaining = fields.Float(
        string="Horas restantes",
        compute="_compute_apreblanc_service_metrics",
    )
    apreblanc_hours_progress = fields.Float(
        string="% consumo",
        compute="_compute_apreblanc_service_metrics",
    )
    apreblanc_hours_deviation = fields.Float(
        string="Desviación",
        compute="_compute_apreblanc_service_metrics",
    )
    apreblanc_profitability_pct = fields.Float(
        string="Rentabilidad estimada %",
        compute="_compute_apreblanc_service_metrics",
    )
    apreblanc_preparation_hours = fields.Float(
        string="Horas preparacion",
        compute="_compute_apreblanc_service_metrics",
    )
    apreblanc_information_hours = fields.Float(
        string="Horas recogida",
        compute="_compute_apreblanc_service_metrics",
    )
    apreblanc_analysis_hours = fields.Float(
        string="Horas analisis",
        compute="_compute_apreblanc_service_metrics",
    )
    apreblanc_report_hours = fields.Float(
        string="Horas informe",
        compute="_compute_apreblanc_service_metrics",
    )

    @api.depends(
        "order_line.apreblanc_target_hours",
        "apreblanc_service_project_id.allocated_hours",
        "apreblanc_service_project_id.remaining_hours",
        "apreblanc_service_project_id.apreblanc_hours_consumed",
        "apreblanc_service_project_id.apreblanc_hours_progress",
        "apreblanc_service_project_id.apreblanc_hours_deviation",
        "apreblanc_service_project_id.apreblanc_profitability_pct",
        "apreblanc_service_project_id.apreblanc_preparation_hours",
        "apreblanc_service_project_id.apreblanc_information_hours",
        "apreblanc_service_project_id.apreblanc_analysis_hours",
        "apreblanc_service_project_id.apreblanc_report_hours",
    )
    def _compute_apreblanc_service_metrics(self):
        for order in self:
            if order.apreblanc_service_project_id:
                project = order.apreblanc_service_project_id
                order.apreblanc_hours_target = project.allocated_hours
                order.apreblanc_hours_consumed = project.apreblanc_hours_consumed
                order.apreblanc_hours_remaining = project.remaining_hours
                order.apreblanc_hours_progress = project.apreblanc_hours_progress
                order.apreblanc_hours_deviation = project.apreblanc_hours_deviation
                order.apreblanc_profitability_pct = project.apreblanc_profitability_pct
                order.apreblanc_preparation_hours = project.apreblanc_preparation_hours
                order.apreblanc_information_hours = project.apreblanc_information_hours
                order.apreblanc_analysis_hours = project.apreblanc_analysis_hours
                order.apreblanc_report_hours = project.apreblanc_report_hours
                continue

            target = sum(order.order_line.filtered(lambda line: not line.display_type).mapped("apreblanc_target_hours"))
            order.apreblanc_hours_target = target
            order.apreblanc_hours_consumed = 0.0
            order.apreblanc_hours_remaining = target
            order.apreblanc_hours_progress = 0.0
            order.apreblanc_hours_deviation = -target
            order.apreblanc_profitability_pct = 100.0 if target else 0.0
            order.apreblanc_preparation_hours = 0.0
            order.apreblanc_information_hours = 0.0
            order.apreblanc_analysis_hours = 0.0
            order.apreblanc_report_hours = 0.0

    def action_confirm(self):
        result = super().action_confirm()
        for order in self:
            if not order.apreblanc_service_project_id:
                order._apreblanc_create_service_project()
        return result

    def _apreblanc_get_service_lines(self):
        self.ensure_one()
        return self.order_line.filtered(
            lambda line: not line.display_type
            and line.product_template_id.detailed_type == "service"
            and line.product_template_id.apreblanc_create_service_project
        )

    def _apreblanc_prepare_project_vals(self, service_lines):
        self.ensure_one()
        return {
            "name": _("%(order)s - %(partner)s", order=self.name, partner=self.partner_id.display_name),
            "partner_id": self.partner_id.id,
            "company_id": self.company_id.id,
            "user_id": self.user_id.id,
            "allow_timesheets": True,
            "allow_task_dependencies": len(service_lines) > 1,
            "allocated_hours": sum(service_lines.mapped("apreblanc_target_hours")),
            "apreblanc_control_enabled": True,
            "apreblanc_sale_order_id": self.id,
            "apreblanc_project_manager_id": self.user_id.id,
        }

    def _apreblanc_get_or_create_project_stages(self):
        self.ensure_one()
        stage_model = self.env["project.task.type"]
        stages = {}
        for stage_name, sequence, fold in APREBLANC_PROJECT_STAGES:
            stage = stage_model.search([("name", "=", stage_name)], limit=1)
            if not stage:
                stage = stage_model.create(
                    {
                        "name": stage_name,
                        "sequence": sequence,
                        "fold": fold,
                    }
                )
            stages[stage_name] = stage
        return stages

    def _apreblanc_prepare_task_vals(self, project, line, default_stage, task_sequence):
        task_name = line.name.splitlines()[0] if line.name else line.product_id.display_name
        return {
            "name": task_name,
            "project_id": project.id,
            "stage_id": default_stage.id,
            "sequence": task_sequence,
            "apreblanc_start_date": line.apreblanc_start_date,
            "partner_id": self.partner_id.id,
            "description": line.name,
            "allocated_hours": line.apreblanc_target_hours,
            "apreblanc_sale_line_id": line.id,
        }

    def _apreblanc_create_service_project(self):
        self.ensure_one()
        if self.apreblanc_service_project_id:
            return self.apreblanc_service_project_id
        service_lines = self._apreblanc_get_service_lines().sorted(lambda line: (line.sequence, line.id))
        if not service_lines:
            return False

        # El proyecto y sus tareas se crean de forma atómica: si falla la
        # creación de las tareas se revierte también el proyecto, evitando dejar
        # un proyecto operativo sin tareas.
        with self.env.cr.savepoint():
            project = self.env["project.project"].create(
                self._apreblanc_prepare_project_vals(service_lines)
            )
            stages = self._apreblanc_get_or_create_project_stages()
            project.write({"type_ids": [(6, 0, [stage.id for stage in stages.values()])]})
            pending_stage = stages["Pendiente de asignar"]
            task_vals = [
                self._apreblanc_prepare_task_vals(
                    project,
                    line,
                    pending_stage,
                    task_sequence=index * 10,
                )
                for index, line in enumerate(service_lines, start=1)
            ]
            tasks = self.env["project.task"].create(task_vals)
            if len(tasks) != len(service_lines):
                raise UserError(
                    _(
                        "No se pudieron crear todas las tareas del proyecto operativo "
                        "para el pedido %(order)s (esperadas %(expected)s, creadas "
                        "%(created)s).",
                        order=self.name,
                        expected=len(service_lines),
                        created=len(tasks),
                    )
                )
            task_by_sale_line = {
                task.apreblanc_sale_line_id.id: task
                for task in tasks.filtered("apreblanc_sale_line_id")
            }
            ordered_tasks = [
                task_by_sale_line[line.id]
                for line in service_lines
                if line.id in task_by_sale_line
            ]
            for previous_task, current_task in zip(ordered_tasks, ordered_tasks[1:]):
                current_task.write({"depend_on_ids": [(4, previous_task.id)]})
            self.apreblanc_service_project_id = project.id

        body = _("Proyecto operativo creado automáticamente desde el pedido confirmado.")
        self.message_post(body=body)
        project.message_post(body=_("Proyecto generado desde el pedido %s.") % self.name)
        return project

    def action_view_apreblanc_service_project(self):
        self.ensure_one()
        if not self.apreblanc_service_project_id:
            raise UserError(_("Este pedido aún no tiene proyecto operativo."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Proyecto operativo"),
            "res_model": "project.project",
            "view_mode": "form",
            "res_id": self.apreblanc_service_project_id.id,
        }
