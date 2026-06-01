from odoo.exceptions import ValidationError

from .common import ExpedientBaseCase


class TestSaleOrder(ExpedientBaseCase):
    def _create_template_with_line(self, **extra_vals):
        vals = {
            "sale_order_template_line_ids": [
                (
                    0,
                    0,
                    {
                        "product_id": self.product.id,
                        "name": "Linea plantilla wizard",
                        "product_uom_qty": 1.0,
                        "product_uom_id": self.product.uom_id.id,
                    },
                )
            ]
        }
        vals.update(extra_vals)
        return self._create_template(**vals)

    def _prepare_named_sale_type_for_expedient(self, expedient_type):
        if "type_id" not in self.env["sale.order"]._fields:
            self.skipTest("El campo type_id no está disponible en sale.order")
        sale_order_type_model = None
        try:
            sale_order_type_model = self.env["sale.order.type"]
        except KeyError:
            self.skipTest("El modelo sale.order.type no está disponible")

        candidate_name = {
            "post_paid": "post-pagado",
            "pre_paid": "pre-pagado",
        }[expedient_type]

        matching_types = sale_order_type_model.search([
            ("name", "ilike", candidate_name),
        ])
        for sale_type in matching_types:
            sale_type.name = f"{sale_type.name} [test {sale_type.id}]"

        while True:
            sale_type = sale_order_type_model.create({"name": candidate_name})
            if sale_type.id not in {2, 3}:
                return sale_type
            sale_type.name = f"{candidate_name} [skip {sale_type.id}]"

    def test_create_sets_pricelist_from_sub_cartera(self):
        pricelist = self.env["product.pricelist"].create(
            {
                "name": "Tarifa Pedido Subcartera",
                "currency_id": self.env.company.currency_id.id,
            }
        )
        sub_cartera = self.env["res.partner"].create(
            {
                "name": "Subcartera Pedido",
                "property_product_pricelist": pricelist.id,
            }
        )

        order = self._create_sale_order(sub_cartera_id=sub_cartera.id)

        self.assertEqual(order.pricelist_id, pricelist)

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

    def test_expedient_create_wizard_uses_resolved_sale_type(self):
        expected_sale_type = self._prepare_named_sale_type_for_expedient("post_paid")
        template = self._create_template_with_line()

        wizard = self.env["expedient.create.wizard"].create(
            {
                "expedient_type": "post_paid",
                "partner_id": self.partner.id,
                "client_id": "CLI-WIZ",
                "expedient_number": "EXP-WIZ",
                "sale_order_template_id": template.id,
            }
        )

        action = wizard.action_create_expedient()
        order = self.env["sale.order"].browse(action["res_id"])

        self.assertTrue(order.exists())
        self.assertEqual(order.type_id, expected_sale_type)

