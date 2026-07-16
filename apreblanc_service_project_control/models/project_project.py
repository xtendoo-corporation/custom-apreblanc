from odoo import _, api, fields, models, tools
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


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
    apreblanc_preparation_hours = fields.Float(
        string="Horas preparacion",
        compute="_compute_apreblanc_phase_hours",
    )
    apreblanc_information_hours = fields.Float(
        string="Horas recogida",
        compute="_compute_apreblanc_phase_hours",
    )
    apreblanc_analysis_hours = fields.Float(
        string="Horas analisis",
        compute="_compute_apreblanc_phase_hours",
    )
    apreblanc_report_hours = fields.Float(
        string="Horas informe",
        compute="_compute_apreblanc_phase_hours",
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
    apreblanc_onedrive_folder_id = fields.Char(
        string="Carpeta OneDrive ID",
        copy=False,
        readonly=True,
        help="ID de la carpeta creada en OneDrive para este proyecto",
    )
    apreblanc_onedrive_folder_name = fields.Char(
        string="Carpeta OneDrive",
        copy=False,
        readonly=True,
        help="Nombre de la carpeta en OneDrive para este proyecto",
    )
    apreblanc_onedrive_error = fields.Boolean(
        string="Error OneDrive",
        default=False,
        copy=False,
        help="Indica si hubo un error al crear la carpeta en OneDrive",
    )
    apreblanc_onedrive_error_message = fields.Text(
        string="Mensaje de error OneDrive",
        copy=False,
        readonly=True,
        help="Detalles del error al crear la carpeta en OneDrive",
    )
    apreblanc_service_type = fields.Selection(
        [
            ("audit", "Auditoría"),
            ("consulting", "Consultoría"),
            ("training", "Formación"),
        ],
        string="Tipo de servicio",
        tracking=True,
        help="Tipo de servicio prestado en este proyecto",
    )
    apreblanc_project_stage = fields.Selection(
        [
            ("complete_audit", "Auditoría Completa"),
            ("follow_up_1", "Primer Seguimiento"),
            ("follow_up_2", "Segundo Seguimiento"),
        ],
        string="Etapa del proyecto",
        default="complete_audit",
        tracking=True,
        help="Etapa actual del proyecto (Auditoría Completa, Primer Seguimiento, Segundo Seguimiento)",
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

    @api.depends("timesheet_ids.unit_amount", "timesheet_ids.apreblanc_task_phase")
    def _compute_apreblanc_phase_hours(self):
        for project in self:
            phase_totals = {
                "preparation": 0.0,
                "information": 0.0,
                "analysis": 0.0,
                "report": 0.0,
            }
            for line in project.timesheet_ids:
                if line.apreblanc_task_phase in phase_totals:
                    phase_totals[line.apreblanc_task_phase] += line.unit_amount
            project.apreblanc_preparation_hours = phase_totals["preparation"]
            project.apreblanc_information_hours = phase_totals["information"]
            project.apreblanc_analysis_hours = phase_totals["analysis"]
            project.apreblanc_report_hours = phase_totals["report"]

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

    @api.model_create_multi
    def create(self, vals_list):
        projects = super().create(vals_list)

        for project in projects.filtered(
            lambda record: record.apreblanc_control_enabled
            and record.apreblanc_sale_order_id
            and not tools.config["test_enable"]
        ):
            try:
                project._create_onedrive_folder()
            except Exception as e:
                _logger.warning(f"⚠️ Error creando carpeta OneDrive para proyecto {project.id}: {str(e)}")
                project.message_post(
                    body=_("Advertencia: No se pudo crear la carpeta en OneDrive. Error: %s") % str(e)
                )

        return projects

    def _get_onedrive_folder_name(self):
        """Generar el nombre de la carpeta en OneDrive"""
        self.ensure_one()

        if self.partner_id and self.name:
            folder_name = f"{self.name} - {self.partner_id.name}"
        elif self.name:
            folder_name = self.name
        else:
            folder_name = f"Proyecto_{self.id}"

        return folder_name

    def _create_onedrive_folder(self):
        """Crear carpeta en OneDrive para el proyecto"""
        self.ensure_one()

        try:
            folder_name = self._get_onedrive_folder_name()
            _logger.info(f"📁 Creando carpeta OneDrive para proyecto {self.id}: '{folder_name}'")

            # Obtener el modelo onedrive.document y el servicio
            try:
                onedrive_doc_model = self.env['onedrive.document']
            except Exception as e:
                _logger.warning(f"⚠️ Modelo onedrive.document no disponible: {e}")
                return

            # Obtener token y headers
            onedrive_service = self.env['onedrive.service']
            token = onedrive_service._get_token()
            headers = {'Authorization': f'Bearer {token}'}

            _logger.info(f"Token obtenido para OneDrive")

            # Crear la carpeta usando el método correcto con headers
            folder_id = onedrive_doc_model._ensure_folder_exists(
                folder_name=folder_name,
                parent_folder_id=None,
                headers=headers
            )

            self.apreblanc_onedrive_folder_id = folder_id
            self.apreblanc_onedrive_folder_name = folder_name
            self.apreblanc_onedrive_error = False
            self.apreblanc_onedrive_error_message = ""

            _logger.info(f"✅ Carpeta OneDrive creada exitosamente: ID={folder_id}, Nombre='{folder_name}'")
            self.message_post(
                body=_("✅ Carpeta OneDrive creada: %s") % folder_name
            )

        except Exception as e:
            error_msg = str(e)
            _logger.error(f"❌ Error al crear carpeta OneDrive: {error_msg}", exc_info=True)

            # Guardar error en el proyecto
            self.apreblanc_onedrive_error = True
            self.apreblanc_onedrive_error_message = error_msg

            self.message_post(
                body=_("❌ Error al crear carpeta OneDrive: %s") % error_msg
            )

    def action_apreblanc_retry_onedrive_folder(self):
        """Reintentar crear la carpeta en OneDrive"""
        for project in self:
            try:
                project._create_onedrive_folder()
            except Exception as e:
                _logger.error(f"Error reintentando crear carpeta OneDrive: {str(e)}")
                project.apreblanc_onedrive_error = True
                project.apreblanc_onedrive_error_message = str(e)
        return True

    def _create_apreblanc_default_tasks(self):
        """Crear las 4 tareas estándar del proyecto"""
        self.ensure_one()
        
        if not self.apreblanc_control_enabled:
            return
        
        # Las 4 tareas estándar que todo proyecto debe tener
        standard_tasks = [
            {"name": _("Trabajo previo"), "sequence": 1},
            {"name": _("Recogida de información"), "sequence": 2},
            {"name": _("Análisis de información"), "sequence": 3},
            {"name": _("Informe"), "sequence": 4},
        ]
        
        task_vals_list = []
        for task_data in standard_tasks:
            task_vals_list.append({
                "name": task_data["name"],
                "project_id": self.id,
                "sequence": task_data["sequence"],
                "partner_id": self.partner_id.id,
                "apreblanc_sale_line_id": False,
            })
        
        if task_vals_list:
            self.env["project.task"].create(task_vals_list)
            _logger.info(f"✅ Se crearon 4 tareas estándar para el proyecto {self.id}")
