from unittest.mock import patch

from odoo.exceptions import UserError

from .common import ServiceProjectControlBaseCase


class TestServiceProjectControl(ServiceProjectControlBaseCase):
    def test_confirm_creates_controlled_project_and_tasks(self):
        order = self._create_sale_order(
            [
                self._line_vals(
                    self.service_product,
                    qty=3,
                    name="Auditoria inicial\nAnalisis y plan de trabajo",
                ),
                self._line_vals(self.material_product, qty=2),
            ]
        )

        order.action_confirm()

        self.assertTrue(order.apreblanc_service_project_id)
        project = order.apreblanc_service_project_id
        self.assertEqual(project.apreblanc_sale_order_id, order)
        self.assertTrue(project.apreblanc_control_enabled)
        self.assertEqual(project.allocated_hours, 7.5)
        self.assertEqual(order.apreblanc_hours_target, 7.5)

        tasks = self.env["project.task"].search([
            ("project_id", "=", project.id),
        ])
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks.name, "Auditoria inicial")
        self.assertEqual(tasks.allocated_hours, 7.5)
        self.assertEqual(tasks.apreblanc_sale_line_id.order_id, order)
        self.assertEqual(tasks.apreblanc_audit_phase, "preparation")

    def test_confirm_without_marked_lines_creates_no_project(self):
        order = self._create_sale_order(
            [
                self._line_vals(self.service_product_no_project, qty=4),
                self._line_vals(self.material_product, qty=2),
            ]
        )

        order.action_confirm()

        self.assertFalse(order.apreblanc_service_project_id)
        self.assertFalse(
            self.env["project.project"].search(
                [("apreblanc_sale_order_id", "=", order.id)]
            )
        )

    def test_confirm_only_includes_marked_service_lines(self):
        order = self._create_sale_order(
            [
                self._line_vals(self.service_product, qty=2, name="Servicio marcado"),
                self._line_vals(
                    self.service_product_no_project, qty=5, name="Servicio no marcado"
                ),
            ]
        )

        order.action_confirm()

        project = order.apreblanc_service_project_id
        self.assertTrue(project)
        tasks = self.env["project.task"].search([("project_id", "=", project.id)])
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks.name, "Servicio marcado")
        self.assertEqual(project.allocated_hours, 5.0)

    def test_confirm_creates_one_task_per_marked_line(self):
        order = self._create_sale_order(
            [
                self._line_vals(self.service_product, qty=1, name="Fase inicial"),
                self._line_vals(self.service_product, qty=1, name="Fase intermedia"),
                self._line_vals(self.service_product, qty=1, name="Fase final"),
            ]
        )

        order.action_confirm()

        project = order.apreblanc_service_project_id
        self.assertTrue(project)
        tasks = self.env["project.task"].search([("project_id", "=", project.id)])
        self.assertEqual(len(tasks), 3, "Debe crearse una tarea por cada línea marcada.")
        self.assertEqual(
            tasks.mapped("apreblanc_sale_line_id"),
            order.order_line,
            "Cada tarea debe quedar vinculada a su línea de venta de origen.",
        )
        self.assertEqual(
            set(tasks.mapped("name")),
            {"Fase inicial", "Fase intermedia", "Fase final"},
        )

    def test_confirm_creates_tasks_even_without_target_hours(self):
        zero_hours_product = self.env["product.product"].create(
            {
                "name": "Servicio marcado sin horas",
                "detailed_type": "service",
                "list_price": 90.0,
                "uom_id": self.product_uom_hour.id,
                "uom_po_id": self.product_uom_hour.id,
                "apreblanc_target_hours": 0.0,
                "apreblanc_create_service_project": True,
            }
        )
        order = self._create_sale_order(
            [self._line_vals(zero_hours_product, qty=2, name="Servicio sin horas")]
        )

        order.action_confirm()

        project = order.apreblanc_service_project_id
        self.assertTrue(project, "Debe crearse el proyecto aunque no haya horas objetivo.")
        tasks = self.env["project.task"].search([("project_id", "=", project.id)])
        self.assertEqual(
            len(tasks),
            1,
            "La tarea debe crearse aunque las horas objetivo sean cero.",
        )
        self.assertEqual(tasks.allocated_hours, 0.0)

    def test_reconfirm_keeps_project_and_tasks(self):
        order = self._create_sale_order(
            [self._line_vals(self.service_product, qty=1, name="Servicio idempotente")]
        )

        order.action_confirm()
        project = order.apreblanc_service_project_id
        tasks_before = self.env["project.task"].search(
            [("project_id", "=", project.id)]
        )
        self.assertEqual(len(tasks_before), 1)

        order._apreblanc_create_service_project()

        self.assertEqual(order.apreblanc_service_project_id, project)
        tasks_after = self.env["project.task"].search(
            [("project_id", "=", project.id)]
        )
        self.assertEqual(
            tasks_after,
            tasks_before,
            "Volver a lanzar la creación no debe duplicar ni perder tareas.",
        )

    def test_task_creation_failure_rolls_back_project(self):
        order = self._create_sale_order(
            [self._line_vals(self.service_product, qty=1, name="Servicio atomico")]
        )

        original_create = type(self.env["project.task"]).create

        def failing_create(self, vals_list):
            raise UserError("Fallo simulado creando tareas")

        with patch.object(type(self.env["project.task"]), "create", failing_create):
            with self.assertRaises(UserError):
                order._apreblanc_create_service_project()

        self.assertFalse(
            order.apreblanc_service_project_id,
            "El pedido no debe quedar enlazado a un proyecto si fallan las tareas.",
        )
        self.assertFalse(
            self.env["project.project"].search(
                [("apreblanc_sale_order_id", "=", order.id)]
            ),
            "No debe quedar ningún proyecto huérfano sin tareas.",
        )

        # Con la creación de tareas restaurada, el proyecto y las tareas se crean.
        self.assertEqual(type(self.env["project.task"]).create, original_create)
        order._apreblanc_create_service_project()
        project = order.apreblanc_service_project_id
        self.assertTrue(project)
        self.assertEqual(
            len(self.env["project.task"].search([("project_id", "=", project.id)])),
            1,
        )

    def test_confirm_creates_sequential_task_dependencies(self):
        order = self._create_sale_order(
            [
                self._line_vals(self.service_product, qty=1, name="Auditoria completa"),
                self._line_vals(self.service_product, qty=1, name="Primera revision"),
                self._line_vals(self.service_product, qty=1, name="Segunda revision"),
            ]
        )

        order.action_confirm()

        project = order.apreblanc_service_project_id
        self.assertTrue(project.allow_task_dependencies)
        tasks = self.env["project.task"].search(
            [("project_id", "=", project.id)],
            order="id asc",
        )
        self.assertEqual(len(tasks), 3)
        self.assertFalse(tasks[0].depend_on_ids)
        self.assertEqual(tasks[1].depend_on_ids, tasks[0])
        self.assertEqual(tasks[2].depend_on_ids, tasks[1])
        self.assertEqual(tasks[1].state, "04_waiting_normal")

    def test_timesheet_overrun_requires_approval(self):
        order = self._create_sale_order(
            [self._line_vals(self.service_product, qty=1, name="Servicio control horas")]
        )
        order.action_confirm()
        project = order.apreblanc_service_project_id
        task = self.env["project.task"].search(
            [("project_id", "=", project.id)],
            limit=1,
        )

        self.env["account.analytic.line"].create(
            {
                "name": "Imputacion dentro de objetivo",
                "project_id": project.id,
                "task_id": task.id,
                "date": "2026-07-07",
                "unit_amount": 2.0,
                "product_uom_id": self.product_uom_hour.id,
                "user_id": self.env.user.id,
            }
        )
        self.assertEqual(project.apreblanc_hours_status, "warning")

        with self.assertRaises(UserError):
            self.env["account.analytic.line"].create(
                {
                    "name": "Imputacion excedida",
                    "project_id": project.id,
                    "task_id": task.id,
                    "date": "2026-07-07",
                    "unit_amount": 1.0,
                    "product_uom_id": self.product_uom_hour.id,
                    "user_id": self.env.user.id,
                }
            )

        project.action_apreblanc_approve_overtime()
        self.assertTrue(project.apreblanc_overtime_approved)

        line = self.env["account.analytic.line"].create(
            {
                "name": "Imputacion aprobada",
                "project_id": project.id,
                "task_id": task.id,
                "date": "2026-07-07",
                "unit_amount": 1.0,
                "product_uom_id": self.product_uom_hour.id,
                "user_id": self.env.user.id,
            }
        )

        self.assertTrue(line)
        self.assertEqual(project.apreblanc_hours_status, "approved")

    def test_timesheet_keeps_task_phase_in_description(self):
        order = self._create_sale_order(
            [self._line_vals(self.service_product, qty=1, name="Servicio con fase")]
        )
        order.action_confirm()

        project = order.apreblanc_service_project_id
        task = self.env["project.task"].search(
            [("project_id", "=", project.id)],
            limit=1,
        )
        task.apreblanc_audit_phase = "information"
        task.apreblanc_audit_phase = "analysis"

        line = self.env["account.analytic.line"].create(
            {
                "name": "Revision documental",
                "project_id": project.id,
                "task_id": task.id,
                "date": "2026-07-07",
                "unit_amount": 1.0,
                "product_uom_id": self.product_uom_hour.id,
                "user_id": self.env.user.id,
            }
        )

        self.assertEqual(line.apreblanc_task_phase, "analysis")
        self.assertEqual(line.name, "[Analisis] Revision documental")

    def test_task_phase_must_advance_without_skipping(self):
        order = self._create_sale_order(
            [self._line_vals(self.service_product, qty=1, name="Servicio con secuencia de fase")]
        )
        order.action_confirm()
        task = self.env["project.task"].search(
            [("project_id", "=", order.apreblanc_service_project_id.id)],
            limit=1,
        )

        task.apreblanc_audit_phase = "information"
        self.assertEqual(task.apreblanc_audit_phase, "information")

        with self.assertRaises(UserError):
            task.apreblanc_audit_phase = "report"

        with self.assertRaises(UserError):
            task.apreblanc_audit_phase = "preparation"

    def test_project_and_order_compute_phase_hours(self):
        order = self._create_sale_order(
            [
                self._line_vals(self.service_product, qty=1, name="Fase 1"),
                self._line_vals(self.service_product, qty=1, name="Fase 2"),
            ]
        )
        order.action_confirm()
        project = order.apreblanc_service_project_id
        tasks = self.env["project.task"].search(
            [("project_id", "=", project.id)],
            order="id asc",
        )
        tasks[0].apreblanc_audit_phase = "information"
        tasks[0].apreblanc_audit_phase = "analysis"
        tasks[1].write({"state": "1_done"})
        tasks[1].apreblanc_audit_phase = "information"
        tasks[1].apreblanc_audit_phase = "analysis"
        tasks[1].apreblanc_audit_phase = "report"

        self.env["account.analytic.line"].create(
            {
                "name": "Trabajo analisis",
                "project_id": project.id,
                "task_id": tasks[0].id,
                "date": "2026-07-07",
                "unit_amount": 1.5,
                "product_uom_id": self.product_uom_hour.id,
                "user_id": self.env.user.id,
            }
        )
        self.env["account.analytic.line"].create(
            {
                "name": "Trabajo informe",
                "project_id": project.id,
                "task_id": tasks[1].id,
                "date": "2026-07-07",
                "unit_amount": 0.5,
                "product_uom_id": self.product_uom_hour.id,
                "user_id": self.env.user.id,
            }
        )

        self.assertEqual(project.apreblanc_analysis_hours, 1.5)
        self.assertEqual(project.apreblanc_report_hours, 0.5)
        self.assertEqual(order.apreblanc_analysis_hours, 1.5)
        self.assertEqual(order.apreblanc_report_hours, 0.5)
