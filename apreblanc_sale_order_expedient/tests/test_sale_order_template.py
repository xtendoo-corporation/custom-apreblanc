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

    def test_template_create_sets_pricelist_from_sub_cartera_when_field_exists(self):
        pricelist = self.env["product.pricelist"].create(
            {
                "name": "Tarifa Subcartera Test",
                "currency_id": self.env.company.currency_id.id,
            }
        )
        sub_cartera = self.env["res.partner"].create(
            {
                "name": "Subcartera Test",
                "property_product_pricelist": pricelist.id,
            }
        )

        template = self._create_template(sub_cartera_id=sub_cartera.id)
        self.assertEqual(template.sub_cartera_id, sub_cartera)
        if "pricelist_id" in template._fields:
            self.assertEqual(template.pricelist_id, pricelist)

    def test_pricelist_from_sub_cartera_overrides_cartera_pricelist(self):
        """La tarifa de la subcartera debe prevalecer sobre la tarifa de la cartera."""
        if "pricelist_id" not in self.env["sale.order.template"]._fields:
            self.skipTest("El módulo no tiene el campo pricelist_id en sale.order.template")

        pricelist_cartera = self.env["product.pricelist"].create(
            {
                "name": "Tarifa Cartera Principal",
                "currency_id": self.env.company.currency_id.id,
            }
        )
        pricelist_subcartera = self.env["product.pricelist"].create(
            {
                "name": "Tarifa Subcartera Específica",
                "currency_id": self.env.company.currency_id.id,
            }
        )

        # La cartera (partner) tiene su propio pricelist
        cartera = self.env["res.partner"].create(
            {
                "name": "Cartera Principal Test",
                "property_product_pricelist": pricelist_cartera.id,
            }
        )

        # La subcartera tiene un pricelist diferente
        sub_cartera = self.env["res.partner"].create(
            {
                "name": "Subcartera Específica Test",
                "property_product_pricelist": pricelist_subcartera.id,
            }
        )

        # Crear plantilla indicando ambas: cartera y subcartera
        template = self.env["sale.order.template"].create(
            {
                "name": "Plantilla Prioridad Subcartera",
                "partner_id": cartera.id,
                "sub_cartera_id": sub_cartera.id,
            }
        )

        self.assertEqual(
            template.pricelist_id,
            pricelist_subcartera,
            "La tarifa debe ser la de la SUBCARTERA, no la de la cartera principal.",
        )
        self.assertNotEqual(
            template.pricelist_id,
            pricelist_cartera,
            "La tarifa de la cartera principal NO debe aplicarse cuando hay subcartera.",
        )

    def test_write_pricelist_from_sub_cartera_overrides_cartera_pricelist(self):
        """Al actualizar sub_cartera_id, la tarifa de la subcartera debe prevalecer."""
        if "pricelist_id" not in self.env["sale.order.template"]._fields:
            self.skipTest("El módulo no tiene el campo pricelist_id en sale.order.template")

        pricelist_cartera = self.env["product.pricelist"].create(
            {
                "name": "Tarifa Cartera Write Test",
                "currency_id": self.env.company.currency_id.id,
            }
        )
        pricelist_subcartera = self.env["product.pricelist"].create(
            {
                "name": "Tarifa Subcartera Write Test",
                "currency_id": self.env.company.currency_id.id,
            }
        )

        cartera = self.env["res.partner"].create(
            {
                "name": "Cartera Write Test",
                "property_product_pricelist": pricelist_cartera.id,
            }
        )
        sub_cartera = self.env["res.partner"].create(
            {
                "name": "Subcartera Write Test",
                "property_product_pricelist": pricelist_subcartera.id,
            }
        )

        # Crear plantilla solo con cartera
        template = self.env["sale.order.template"].create(
            {
                "name": "Plantilla Write Subcartera",
                "partner_id": cartera.id,
            }
        )

        # Asignar la subcartera mediante write (sin pasar pricelist_id explícito)
        template.write({"sub_cartera_id": sub_cartera.id})

        self.assertEqual(
            template.pricelist_id,
            pricelist_subcartera,
            "Tras write, la tarifa debe ser la de la SUBCARTERA.",
        )
        self.assertNotEqual(
            template.pricelist_id,
            pricelist_cartera,
            "Tras write, la tarifa de la cartera NO debe prevalecer sobre la subcartera.",
        )

    def test_template_pricelist_falls_back_to_odoo_default_when_sub_cartera_and_partner_have_none(self):
        if "pricelist_id" not in self.env["sale.order.template"]._fields:
            self.skipTest("El módulo no tiene el campo pricelist_id en sale.order.template")

        partner = self.env["res.partner"].create(
            {
                "name": "Partner Fallback Test",
            }
        )
        sub_cartera = self.env["res.partner"].create(
            {
                "name": "Subcartera Sin Tarifa",
            }
        )
        default_pricelist = self.env["sale.order"].new(
            {"partner_id": partner.id}
        ).pricelist_id

        template = self.env["sale.order.template"].create(
            {
                "name": "Plantilla Fallback Partner",
                "partner_id": partner.id,
                "sub_cartera_id": sub_cartera.id,
            }
        )

        self.assertEqual(
            template.pricelist_id,
            default_pricelist,
            "La tarifa debe caer a la predeterminada de Odoo cuando no haya una específica.",
        )

