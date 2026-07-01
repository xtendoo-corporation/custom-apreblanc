from odoo import fields

from .common import ExpedientBaseCase


class TestSaleOrderExpedientReturnHistory(ExpedientBaseCase):
    def test_default_get_sets_return_date_and_user(self):
        defaults = self.env["sale.order.expedient.return.history"].default_get(
            ["return_date", "user_id"]
        )

        self.assertIn("return_date", defaults)
        self.assertEqual(defaults.get("user_id"), self.env.user.id)

    def test_create_moves_expedient_to_pending_documentation(self):
        order = self._create_sale_order(
            expedient_type="post_paid",
            expedient_state="creada",
            person_under_study_id=self.study_partner.id,
            person_type="fisica",
            expedient_difficulty="simple",
            deadline="24",
        )

        self.env["sale.order.expedient.return.history"].create(
            {
                "sale_order_id": order.id,
                "return_date": fields.Datetime.now(),
                "return_reason_id": self.return_reason.id,
            }
        )

        self.assertEqual(order.expedient_state, "pendiente_documentacion")

    def test_create_posts_message_in_sale_order_chatter(self):
        order = self._create_sale_order(
            expedient_type="post_paid",
            expedient_state="creada",
            person_under_study_id=self.study_partner.id,
            person_type="fisica",
            expedient_difficulty="simple",
            deadline="24",
        )

        self.env["sale.order.expedient.return.history"].create(
            {
                "sale_order_id": order.id,
                "return_date": fields.Datetime.now(),
                "return_reason_id": self.return_reason.id,
                "notes": "faltan pdf",
            }
        )

        message = self.env["mail.message"].search(
            [
                ("model", "=", "sale.order"),
                ("res_id", "=", order.id),
                ("body", "ilike", "Devolución registrada"),
            ],
            order="id desc",
            limit=1,
        )

        self.assertTrue(message)
        self.assertIn("Falta documentacion", message.body)
        self.assertIn("faltan pdf", message.body)

