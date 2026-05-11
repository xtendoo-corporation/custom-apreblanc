from .common import ExpedientBaseCase


class TestSaleOrderTemplateLine(ExpedientBaseCase):
    def _create_template_with_line(self, application_rule=None):
        template = self._create_template(
            sale_order_template_line_ids=[
                (
                    0,
                    0,
                    {
                        "product_id": self.product.id,
                        "name": "Linea plantilla",
                        "product_uom_qty": 1.0,
                        "product_uom_id": self.product.uom_id.id,
                        "application_rule": application_rule,
                    },
                )
            ]
        )
        return template, template.sale_order_template_line_ids[:1]

    def test_should_apply_without_rule_returns_true(self):
        template, line = self._create_template_with_line()
        order = self._create_sale_order(sale_order_template_id=template.id)

        self.assertTrue(line._should_apply(order))

    def test_should_apply_with_valid_rule_returns_true(self):
        template, line = self._create_template_with_line(
            "order.expedient_type == 'post_paid'"
        )
        order = self._create_sale_order(
            sale_order_template_id=template.id,
            expedient_type="post_paid",
        )

        self.assertTrue(line._should_apply(order))

    def test_should_apply_with_invalid_rule_returns_false(self):
        template, line = self._create_template_with_line("1/0")
        order = self._create_sale_order(sale_order_template_id=template.id)

        self.assertFalse(line._should_apply(order))

    def test_should_apply_with_and_rule_positive_and_negative(self):
        template, line = self._create_template_with_line(
            "order.expedient_type == 'post_paid' and order.person_type == 'fisica'"
        )

        valid_order = self._create_sale_order(
            sale_order_template_id=template.id,
            expedient_type="post_paid",
            person_type="fisica",
        )
        invalid_order = self._create_sale_order(
            sale_order_template_id=template.id,
            expedient_type="post_paid",
            person_type="juridica",
        )

        self.assertTrue(line._should_apply(valid_order))
        self.assertFalse(line._should_apply(invalid_order))

