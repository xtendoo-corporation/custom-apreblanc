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
