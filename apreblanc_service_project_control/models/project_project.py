from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ProjectProject(models.Model):
    _inherit = "project.project"

    apreblanc_control_enabled = fields.Boolean(
        string="Control Apreblanc",
        default=False,
        copy=False,
    )
    apreblanc_sale_order_id = fields.Many2one(
        "sale.order",
        string="Pedido origen",
        copy=False,
        readonly=True,
        index=True,
    )
    apreblanc_project_manager_id = fields.Many2one(
        "res.users",
        string="Jefe de proyecto",
        tracking=True,
    )
    apreblanc_junior_user_id = fields.Many2one(
        "res.users",
        string="Gestor junior",
        tracking=True,
    )
    apreblanc_senior_user_id = fields.Many2one(
        "res.users",
        string="Gestor senior",
        tracking=True,
    )
    apreblanc_hours_consumed = fields.Float(
        string="Horas consumidas",
        compute="_compute_apreblanc_hours_metrics",
    )
    apreblanc_hours_progress = fields.Float(
        string="% consumo",
        compute="_compute_apreblanc_hours_metrics",
    )
    apreblanc_hours_deviation = fields.Float(
        string="Desviación",
        compute="_compute_apreblanc_hours_metrics",
    )
    apreblanc_profitability_pct = fields.Float(
        string="Rentabilidad estimada %",
        compute="_compute_apreblanc_hours_metrics",
    )
    apreblanc_hours_status = fields.Selection(
        [
            ("normal", "Dentro de objetivo"),
            ("warning", "En umbral"),
            ("exceeded", "Excedido"),
            ("approved", "Excedido autorizado"),
        ],
        string="Estado horas",
        compute="_compute_apreblanc_hours_metrics",
    )
    apreblanc_overtime_approved = fields.Boolean(
        string="Exceso autorizado",
        default=False,
        copy=False,
    )
    apreblanc_overtime_approved_by = fields.Many2one(
        "res.users",
        string="Autorizado por",
        copy=False,
        readonly=True,
    )
    apreblanc_overtime_approved_date = fields.Datetime(
        string="Fecha autorización",
        copy=False,
        readonly=True,
    )

    @api.depends("allocated_hours", "timesheet_ids.unit_amount", "apreblanc_overtime_approved")
    def _compute_apreblanc_hours_metrics(self):
        for project in self:
            consumed = sum(project.timesheet_ids.mapped("unit_amount"))
            target = project.allocated_hours or 0.0
            project.apreblanc_hours_consumed = consumed
            project.apreblanc_hours_deviation = consumed - target
            project.apreblanc_hours_progress = target and (consumed / target) * 100.0 or 0.0
            if consumed <= 0 or target <= 0:
                project.apreblanc_profitability_pct = 100.0 if target > 0 else 0.0
            elif consumed <= target:
                project.apreblanc_profitability_pct = 100.0
            else:
                project.apreblanc_profitability_pct = round((target / consumed) * 100.0, 2)

            if not target:
                project.apreblanc_hours_status = "normal"
            elif consumed > target:
                project.apreblanc_hours_status = (
                    "approved" if project.apreblanc_overtime_approved else "exceeded"
                )
            elif consumed >= target * 0.8:
                project.apreblanc_hours_status = "warning"
            else:
                project.apreblanc_hours_status = "normal"

    def _check_apreblanc_overtime_authorization(self):
        self.ensure_one()
        if self.env.user == self.apreblanc_project_manager_id:
            return
        if self.env.user.has_group("project.group_project_manager"):
            return
        if self.env.user.has_group("base.group_system"):
            return
        raise UserError(
            _("Solo el jefe de proyecto o un responsable con permisos puede autorizar el exceso de horas.")
        )

    def action_apreblanc_approve_overtime(self):
        for project in self:
            project._check_apreblanc_overtime_authorization()
            project.write(
                {
                    "apreblanc_overtime_approved": True,
                    "apreblanc_overtime_approved_by": self.env.user.id,
                    "apreblanc_overtime_approved_date": fields.Datetime.now(),
                }
            )
            project.message_post(body=_("Exceso horario autorizado por %s.") % self.env.user.name)
        return True

    def action_apreblanc_reset_overtime(self):
        for project in self:
            project._check_apreblanc_overtime_authorization()
            project.write(
                {
                    "apreblanc_overtime_approved": False,
                    "apreblanc_overtime_approved_by": False,
                    "apreblanc_overtime_approved_date": False,
                }
            )
            project.message_post(body=_("Se revoca la autorización de exceso horario."))
        return True

    def action_view_apreblanc_sale_order(self):
        self.ensure_one()
        if not self.apreblanc_sale_order_id:
            raise UserError(_("Este proyecto no tiene pedido de venta origen."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Pedido origen"),
            "res_model": "sale.order",
            "view_mode": "form",
            "res_id": self.apreblanc_sale_order_id.id,
        }
