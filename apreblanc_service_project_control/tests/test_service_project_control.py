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
