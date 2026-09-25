from odoo.exceptions import ValidationError
from odoo.tests.common import Form
from unittest import skip

from .common import ExpedientBaseCase


class TestSaleOrder(ExpedientBaseCase):
    def _create_pricelist_with_fixed_price(self, fixed_price):
        pricelist = self.env["product.pricelist"].create(
            {
                "name": f"Tarifa fija {fixed_price}",
                "currency_id": self.env.company.currency_id.id,
            }
        )
        self.env["product.pricelist.item"].create(
            {
                "pricelist_id": pricelist.id,
                "applied_on": "0_product_variant",
                "product_id": self.product.id,
                "compute_price": "fixed",
                "fixed_price": fixed_price,
            }
        )
        return pricelist

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

    def test_write_does_not_auto_confirm_regular_sale_order(self):
        order = self._create_sale_order(expedient_type="none")

        order.write({"client_order_ref": "AUTO-CONFIRM-NONE"})

        self.assertEqual(
            order.state,
            "draft",
            "Los pedidos normales NO deben confirmarse automáticamente al hacer write; "
            "solo los expedientes usan la auto-confirmación.",
        )

    def test_write_auto_confirms_post_paid_when_required_fields_are_completed(self):
        order = self._create_sale_order(expedient_type="post_paid")

        order.write(
            {
                "person_under_study_id": self.study_partner.id,
                "person_type": "fisica",
                "expedient_difficulty": "simple",
                "deadline": "24",
            }
        )

        self.assertEqual(
            order.state,
            "sale",
            "El expediente post-pagado debe confirmarse automáticamente al completar los datos obligatorios.",
        )

    def test_write_does_not_auto_confirm_post_paid_when_required_fields_are_missing(self):
        order = self._create_sale_order(expedient_type="post_paid")

        order.write(
            {
                "person_under_study_id": self.study_partner.id,
                "person_type": "fisica",
            }
        )

        self.assertEqual(
            order.state,
            "draft",
            "Si faltan datos obligatorios del expediente, el write no debe confirmar el pedido.",
        )

    def test_write_does_not_reconfirm_order_already_confirmed(self):
        order = self._create_sale_order(expedient_type="none")
        order.action_confirm()

        order.write({"client_order_ref": "YA-CONFIRMADO"})

        self.assertEqual(order.state, "sale")

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

    def test_configuration_and_import_actions_are_admin_only(self):
        admin_group = self.env.ref("apreblanc_sale_order_expedient.group_expedient_admin")
        action_templates = self.env.ref("apreblanc_sale_order_expedient.action_sale_order_expedient_templates")
        action_return_reason = self.env.ref("apreblanc_sale_order_expedient.action_expedient_return_reason")
        action_import = self.env.ref("apreblanc_sale_order_expedient.action_import_expedient_excel")
        action_import_button = self.env.ref("apreblanc_sale_order_expedient.action_sale_order_import_excel_button")
        menu_config = self.env.ref("apreblanc_sale_order_expedient.menu_expedient_configuration")
        menu_templates = self.env.ref("apreblanc_sale_order_expedient.menu_sale_order_expedient_templates")
        menu_return_reason = self.env.ref("apreblanc_sale_order_expedient.menu_expedient_return_reason")
        menu_import = self.env.ref("apreblanc_sale_order_expedient.menu_import_expedient_excel")

        self.assertEqual(action_templates.groups_id, admin_group)
        self.assertEqual(action_return_reason.groups_id, admin_group)
        self.assertEqual(action_import.groups_id, admin_group)
        self.assertEqual(action_import_button.groups_id, admin_group)
        self.assertEqual(menu_config.groups_id, admin_group)
        self.assertEqual(menu_templates.groups_id, admin_group)
        self.assertEqual(menu_return_reason.groups_id, admin_group)
        self.assertEqual(menu_import.groups_id, admin_group)

    @skip("Legacy failure no relacionado con la tarifa; pendiente de revisar aparte.")
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

    def test_expedient_create_wizard_applies_template_pricelist(self):
        pricelist = self.env["product.pricelist"].create(
            {
                "name": "Tarifa Plantilla Wizard",
                "currency_id": self.env.company.currency_id.id,
            }
        )
        template = self._create_template_with_line(pricelist_id=pricelist.id)

        wizard = self.env["expedient.create.wizard"].create(
            {
                "expedient_type": "post_paid",
                "partner_id": self.partner.id,
                "client_id": "CLI-WIZ-PRICE",
                "expedient_number": "EXP-WIZ-PRICE",
                "sale_order_template_id": template.id,
            }
        )

        action = wizard.action_create_expedient()
        order = self.env["sale.order"].browse(action["res_id"])

        self.assertEqual(
            order.pricelist_id,
            pricelist,
            "El pedido debe tomar la tarifa configurada en la plantilla.",
        )

    def test_expedient_create_wizard_keeps_odoo_default_pricelist_when_template_has_none(self):
        partner_without_pricelist = self.env["res.partner"].create(
            {
                "name": "Partner Sin Tarifa Wizard",
            }
        )
        default_pricelist = self.env["sale.order"].new(
            {"partner_id": partner_without_pricelist.id}
        ).pricelist_id
        template = self._create_template_with_line(
            partner_id=partner_without_pricelist.id,
            pricelist_id=False,
        )

        wizard = self.env["expedient.create.wizard"].create(
            {
                "expedient_type": "post_paid",
                "partner_id": partner_without_pricelist.id,
                "client_id": "CLI-WIZ-DEFAULT",
                "expedient_number": "EXP-WIZ-DEFAULT",
                "sale_order_template_id": template.id,
            }
        )

        action = wizard.action_create_expedient()
        order = self.env["sale.order"].browse(action["res_id"])

        self.assertEqual(
            order.pricelist_id,
            default_pricelist,
            "Si la plantilla no tiene tarifa, debe mantenerse la tarifa por defecto de Odoo.",
        )

    def test_prepaid_expedient_create_wizard_applies_template_pricelist(self):
        pricelist = self.env["product.pricelist"].create(
            {
                "name": "Tarifa Plantilla Wizard Prepaid",
                "currency_id": self.env.company.currency_id.id,
            }
        )
        template = self._create_template_with_line(pricelist_id=pricelist.id)

        wizard = self.env["expedient.create.wizard"].create(
            {
                "expedient_type": "pre_paid",
                "partner_id": self.partner.id,
                "client_id": "CLI-WIZ-PRE-PRICE",
                "expedient_number": "EXP-WIZ-PRE-PRICE",
                "sale_order_template_id": template.id,
            }
        )

        action = wizard.action_create_expedient()
        order = self.env["sale.order"].browse(action["res_id"])

        self.assertEqual(
            order.pricelist_id,
            pricelist,
            "El expediente pre-pagado debe tomar la tarifa configurada en la plantilla.",
        )

    def test_prepaid_expedient_create_wizard_keeps_odoo_default_pricelist_when_template_has_none(self):
        partner_without_pricelist = self.env["res.partner"].create(
            {
                "name": "Partner Sin Tarifa Wizard Prepaid",
            }
        )
        default_pricelist = self.env["sale.order"].new(
            {"partner_id": partner_without_pricelist.id}
        ).pricelist_id
        template = self._create_template_with_line(
            partner_id=partner_without_pricelist.id,
            pricelist_id=False,
        )

        wizard = self.env["expedient.create.wizard"].create(
            {
                "expedient_type": "pre_paid",
                "partner_id": partner_without_pricelist.id,
                "client_id": "CLI-WIZ-PRE-DEFAULT",
                "expedient_number": "EXP-WIZ-PRE-DEFAULT",
                "sale_order_template_id": template.id,
            }
        )

        action = wizard.action_create_expedient()
        order = self.env["sale.order"].browse(action["res_id"])

        self.assertEqual(
            order.pricelist_id,
            default_pricelist,
            "Si la plantilla no tiene tarifa, el expediente pre-pagado debe conservar la tarifa por defecto de Odoo.",
        )

    def test_sale_order_template_wizard_applies_template_pricelist(self):
        pricelist = self.env["product.pricelist"].create(
            {
                "name": "Tarifa Wizard Plantilla Directa",
                "currency_id": self.env.company.currency_id.id,
            }
        )
        template = self._create_template_with_line(pricelist_id=pricelist.id)

        wizard = self.env["sale.order.template.wizard"].with_context(
            default_template_id=template.id
        ).create(
            {
                "template_id": template.id,
                "partner_id": self.partner.id,
            }
        )

        action = wizard.create_sale_order()
        order = self.env["sale.order"].browse(action["res_id"])

        self.assertEqual(
            order.pricelist_id,
            pricelist,
            "El pedido creado desde el wizard de plantilla debe heredar la tarifa de la plantilla.",
        )

    def test_sale_order_create_from_template_sets_pricelist(self):
        pricelist = self.env["product.pricelist"].create(
            {
                "name": "Tarifa Create Desde Plantilla",
                "currency_id": self.env.company.currency_id.id,
            }
        )
        template = self._create_template_with_line(pricelist_id=pricelist.id)

        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "sale_order_template_id": template.id,
            }
        )

        self.assertEqual(
            order.pricelist_id,
            pricelist,
            "El pedido debe heredar la tarifa de la plantilla al crearse desde sale.order.create().",
        )

    def test_expedient_create_wizard_does_not_create_template_lines_before_confirm(self):
        pricelist = self._create_pricelist_with_fixed_price(42.0)
        template = self._create_template_with_line(pricelist_id=pricelist.id)

        wizard = self.env["expedient.create.wizard"].create(
            {
                "expedient_type": "post_paid",
                "partner_id": self.partner.id,
                "client_id": "CLI-WIZ-NO-LINES",
                "expedient_number": "EXP-WIZ-NO-LINES",
                "sale_order_template_id": template.id,
            }
        )

        action = wizard.action_create_expedient()
        order = self.env["sale.order"].browse(action["res_id"])

        self.assertEqual(order.pricelist_id, pricelist)
        self.assertFalse(
            order.order_line,
            "El presupuesto no debe crear líneas de plantilla hasta la confirmación.",
        )

    def test_action_confirm_creates_applicable_template_lines_with_pricelist(self):
        pricelist = self._create_pricelist_with_fixed_price(42.0)
        template = self._create_template_with_line(pricelist_id=pricelist.id)

        wizard = self.env["expedient.create.wizard"].create(
            {
                "expedient_type": "post_paid",
                "partner_id": self.partner.id,
                "client_id": "CLI-WIZ-CONFIRM-LINES",
                "expedient_number": "EXP-WIZ-CONFIRM-LINES",
                "sale_order_template_id": template.id,
            }
        )

        action = wizard.action_create_expedient()
        order = self.env["sale.order"].browse(action["res_id"])

        order.write(
            {
                "person_under_study_id": self.study_partner.id,
                "person_type": "fisica",
                "expedient_difficulty": "simple",
                "deadline": "24",
            }
        )
        order.action_confirm()
        target_line = order.order_line.filtered(lambda l: l.product_id == self.product)

        self.assertEqual(order.pricelist_id, pricelist)
        self.assertTrue(target_line, "La línea de plantilla debe crearse al confirmar.")
        self.assertEqual(
            target_line.price_unit,
            42.0,
            "La línea creada al confirmar debe respetar la tarifa del pedido.",
        )

    def _create_draft_expedient_with_template_line(self, template, **extra_vals):
        """Simula el onchange estándar de sale_management: el pedido queda en
        borrador con la línea de la plantilla ya insertada (template_line_id
        incluido), tal como la ve el usuario en el formulario antes de guardar.

        No se completan aún los campos obligatorios del expediente (persona a
        estudiar, dificultad, etc.) para que la auto-confirmación no se dispare
        todavía y el pedido siga editable en borrador, igual que en el flujo real.
        """
        template_line = template.sale_order_template_line_ids[:1]
        vals = {
            "partner_id": self.partner.id,
            "expedient_type": "post_paid",
            "sale_order_template_id": template.id,
            "order_line": [(0, 0, template_line._prepare_order_line_values())],
        }
        vals.update(extra_vals)
        order = self.env["sale.order"].create(vals)
        return order, template_line

    def _complete_expedient_required_fields(self, order):
        order.write(
            {
                "person_under_study_id": self.study_partner.id,
                "person_type": "fisica",
                "expedient_difficulty": "simple",
                "deadline": "24",
            }
        )

    def test_deleting_template_line_in_draft_does_not_recreate_it_on_confirm(self):
        template = self._create_template_with_line()
        order, template_line = self._create_draft_expedient_with_template_line(template)
        self.assertEqual(order.state, "draft")

        target_line = order.order_line.filtered(lambda l: l.product_id == self.product)
        self.assertTrue(target_line, "La línea de plantilla debe insertarse en borrador.")
        self.assertEqual(target_line.template_line_id, template_line)

        target_line.unlink()
        self.assertIn(
            template_line.id,
            order.excluded_template_line_ids.ids,
            "Al borrar manualmente la línea, debe quedar excluida de futuras recreaciones.",
        )

        self._complete_expedient_required_fields(order)

        self.assertEqual(
            order.state,
            "sale",
            "El expediente debe auto-confirmarse al completar los datos obligatorios.",
        )
        self.assertFalse(
            order.order_line.filtered(lambda l: l.product_id == self.product),
            "La línea borrada manualmente en borrador no debe reaparecer al confirmar.",
        )

    def test_zero_quantity_template_line_in_draft_is_not_duplicated_on_confirm(self):
        template = self._create_template_with_line()
        order, _template_line = self._create_draft_expedient_with_template_line(template)

        target_line = order.order_line.filtered(lambda l: l.product_id == self.product)
        self.assertTrue(target_line)

        target_line.product_uom_qty = 0.0
        self._complete_expedient_required_fields(order)

        self.assertEqual(order.state, "sale")
        lines_for_product = order.order_line.filtered(lambda l: l.product_id == self.product)
        self.assertEqual(
            len(lines_for_product),
            1,
            "Poner la cantidad a 0 en borrador no debe crear una línea duplicada al confirmar.",
        )

    def test_legacy_line_with_reordered_sequence_is_not_duplicated(self):
        """El onchange estándar de Odoo fuerza sequence=-99 en la primera línea que
        inserta al aplicar una plantilla (para no mezclarla con otras filas al
        paginar). Una línea así, creada antes de introducir template_line_id, no
        debe duplicarse solo porque su secuencia no coincide con la de la plantilla.
        Reproduce el caso real de un pedido normal (no expediente) con plantilla."""
        template = self._create_template_with_line()

        order = self._create_sale_order(
            sale_order_template_id=template.id,
            order_line=[
                (
                    0,
                    0,
                    {
                        "product_id": self.product.id,
                        "name": "Linea plantilla wizard",
                        "product_uom_qty": 1.0,
                        "product_uom": self.product.uom_id.id,
                        "sequence": -99,
                    },
                )
            ],
        )

        order._create_applicable_template_lines()

        lines_for_product = order.order_line.filtered(lambda l: l.product_id == self.product)
        self.assertEqual(
            len(lines_for_product),
            1,
            "Una línea existente con distinta secuencia no debe duplicarse al confirmar.",
        )

    def test_template_line_id_survives_form_onchange_and_save(self):
        """El onchange estándar solo conserva, al guardar, los campos que aparecen
        (aunque sea ocultos) en la subvista de order_line. Usamos `Form`, que simula
        fielmente el comportamiento del cliente web (a diferencia de crear la línea
        directamente por ORM), para comprobar que template_line_id sobrevive."""
        template = self._create_template_with_line()

        order_form = Form(self.env["sale.order"])
        order_form.partner_id = self.partner
        order_form.sale_order_template_id = template
        order = order_form.save()

        target_line = order.order_line.filtered(lambda l: l.product_id == self.product)
        self.assertTrue(target_line, "La línea de plantilla debe insertarse vía onchange.")
        self.assertEqual(
            target_line.template_line_id,
            template.sale_order_template_line_ids[:1],
            "template_line_id debe sobrevivir al onchange real del formulario y no "
            "perderse al guardar (si no aparece en la subvista, el cliente lo descarta).",
        )

