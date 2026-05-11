from odoo.exceptions import ValidationError

from .common import ExpedientBaseCase


class TestSaleOrder(ExpedientBaseCase):
    def test_create_prepaid_forces_sale_and_creada(self):
        order = self._create_sale_order(expedient_type="pre_paid")

        self.assertEqual(order.state, "sale")
        self.assertEqual(order.expedient_state, "creada")
        self.assertTrue(order.expedient_date_start)

    def test_action_confirm_requires_expedient_fields(self):
        order = self._create_sale_order(expedient_type="post_paid")

        with self.assertRaises(ValidationError):
            order.action_confirm()

    def test_action_expedient_aprobada_sets_end_date_and_sale_state(self):
        order = self._create_sale_order(
            expedient_type="post_paid",
            person_under_study_id=self.study_partner.id,
            person_type="fisica",
            expedient_difficulty="simple",
            deadline="24",
        )

        order.action_expedient_aprobada()

        self.assertEqual(order.state, "sale")
        self.assertEqual(order.expedient_state, "aprobada")
        self.assertTrue(order.expedient_date_end)

    def test_action_register_return_creates_history_and_clears_fields(self):
        order = self._create_sale_order(
            expedient_type="pre_paid",
            return_reason_id=self.return_reason.id,
            return_notes="Test notes",
        )

        order.action_register_return()

        self.assertEqual(len(order.expedient_return_history_ids), 1)
        self.assertEqual(order.expedient_state, "pendiente_documentacion")
        self.assertFalse(order.return_reason_id)
        self.assertFalse(order.return_notes)

    def test_cron_update_missing_expedient_end_dates(self):
        order = self._create_sale_order(
            expedient_type="post_paid",
            person_under_study_id=self.study_partner.id,
            person_type="fisica",
            expedient_difficulty="simple",
            deadline="24",
        )
        order.action_expedient_aprobada()

        self.env.cr.execute(
            "UPDATE sale_order SET expedient_date_end = NULL WHERE id = %s", (order.id,)
        )
        order = self.env["sale.order"].browse(order.id)
        order.invalidate_recordset(["expedient_state", "expedient_date_end"])
        self.assertFalse(order.expedient_date_end)

        updated = self.env["sale.order"]._cron_update_missing_expedient_end_dates()
        order.invalidate_recordset(["expedient_date_end"])

        self.assertIsInstance(updated, int)
        self.assertTrue(order.expedient_date_end)

    def test_positive_values_constraint(self):
        order = self._create_sale_order(expedient_type="post_paid")

        with self.assertRaises(ValidationError):
            order.write({"parts_involved": 0})

