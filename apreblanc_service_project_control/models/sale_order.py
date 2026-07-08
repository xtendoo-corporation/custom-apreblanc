from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = "sale.order"

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

    @api.depends(
        "order_line.apreblanc_target_hours",
        "apreblanc_service_project_id.allocated_hours",
        "apreblanc_service_project_id.remaining_hours",
        "apreblanc_service_project_id.apreblanc_hours_consumed",
        "apreblanc_service_project_id.apreblanc_hours_progress",
        "apreblanc_service_project_id.apreblanc_hours_deviation",
        "apreblanc_service_project_id.apreblanc_profitability_pct",
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
                continue

            target = sum(order.order_line.filtered(lambda line: not line.display_type).mapped("apreblanc_target_hours"))
            order.apreblanc_hours_target = target
            order.apreblanc_hours_consumed = 0.0
            order.apreblanc_hours_remaining = target
            order.apreblanc_hours_progress = 0.0
            order.apreblanc_hours_deviation = -target
            order.apreblanc_profitability_pct = 100.0 if target else 0.0

    def action_confirm(self):
        result = super().action_confirm()
        for order in self:
            if not order.apreblanc_service_project_id:
                order._apreblanc_create_service_project()
        return result

    def _apreblanc_get_service_lines(self):
        self.ensure_one()
        return self.order_line.filtered(
            lambda line: not line.display_type and line.product_template_id.detailed_type == "service"
        )

    def _apreblanc_prepare_project_vals(self, service_lines):
        self.ensure_one()
        return {
            "name": _("%(order)s - %(partner)s", order=self.name, partner=self.partner_id.display_name),
            "partner_id": self.partner_id.id,
            "company_id": self.company_id.id,
            "user_id": self.user_id.id,
            "allow_timesheets": True,
            "allocated_hours": sum(service_lines.mapped("apreblanc_target_hours")),
            "apreblanc_control_enabled": True,
            "apreblanc_sale_order_id": self.id,
            "apreblanc_project_manager_id": self.user_id.id,
        }

    def _apreblanc_prepare_task_vals(self, project, line):
        task_name = line.name.splitlines()[0] if line.name else line.product_id.display_name
        return {
            "name": task_name,
            "project_id": project.id,
            "partner_id": self.partner_id.id,
            "description": line.name,
            "allocated_hours": line.apreblanc_target_hours,
            "apreblanc_sale_line_id": line.id,
        }

    def _apreblanc_create_service_project(self):
        self.ensure_one()
        service_lines = self._apreblanc_get_service_lines()
        if not service_lines:
            return False

        project = self.env["project.project"].create(
            self._apreblanc_prepare_project_vals(service_lines)
        )
        task_vals = [self._apreblanc_prepare_task_vals(project, line) for line in service_lines]
        self.env["project.task"].create(task_vals)
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
