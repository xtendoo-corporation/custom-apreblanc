from .common import ExpedientBaseCase


class TestSaleOrderTemplate(ExpedientBaseCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.group_user = cls.env.ref("base.group_user")
        cls.group_system = cls.env.ref("base.group_system")
        cls.group_sales = cls.env.ref("sales_team.group_sale_salesman")
        cls.limited_user = cls.env["res.users"].with_context(no_reset_password=True).create(
            {
                "name": "Limited User",
                "login": "limited_user_template_test",
                "email": "limited@example.com",
                "groups_id": [(6, 0, [cls.group_user.id, cls.group_sales.id])],
            }
        )

    def test_is_restricted_compute(self):
        template = self._create_template()
        self.assertFalse(template.is_restricted)

        template.allowed_group_ids = [(6, 0, [self.group_user.id])]
        self.assertTrue(template.is_restricted)

    def test_can_use_template_for_current_user(self):
        template = self._create_template(allowed_group_ids=[(6, 0, [self.group_system.id])])
        self.assertTrue(template.can_use_template)

    def test_search_filters_restricted_templates_for_non_admin(self):
        open_template = self._create_template(name="Open T")
        restricted_template = self._create_template(
            name="Restricted T",
            allowed_group_ids=[(6, 0, [self.group_system.id])],
        )

        records_for_limited = self.env["sale.order.template"].with_user(
            self.limited_user
        ).search([])

        self.assertIn(open_template, records_for_limited)
        self.assertNotIn(restricted_template, records_for_limited)

