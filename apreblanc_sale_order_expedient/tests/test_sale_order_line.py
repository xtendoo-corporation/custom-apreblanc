from odoo.tests.common import Form

from .common import ExpedientBaseCase


class TestSaleOrderLine(ExpedientBaseCase):
    def test_manual_price_unit_survives_quantity_change_in_same_form_session(self):
        """Reproduce el bug reportado: editar el precio unitario a mano y luego
        cambiar la cantidad en la misma línea no debe resetear el precio. Se usa
        Form() porque reproduce fielmente el ciclo de onchange real del cliente
        web; con create()/write() directos por ORM no se reproduce el bug."""
        order_form = Form(self.env["sale.order"])
        order_form.partner_id = self.partner
        with order_form.order_line.new() as line:
            line.product_id = self.product

        with order_form.order_line.edit(0) as line:
            original_price = line.price_unit
            line.price_unit = original_price + 37.0

        with order_form.order_line.edit(0) as line:
            line.product_uom_qty = 3.0

        order = order_form.save()

        saved_line = order.order_line.filtered(lambda l: l.product_id == self.product)
        self.assertEqual(
            saved_line.price_unit,
            original_price + 37.0,
            "El precio unitario editado manualmente no debe resetearse al "
            "cambiar la cantidad en la misma sesión del formulario.",
        )
        self.assertEqual(saved_line.product_uom_qty, 3.0)

    def test_changing_product_resets_manual_price_protection(self):
        """Cambiar de producto sí debe volver a calcular el precio desde la
        tarifa, aunque antes se hubiera fijado un precio manual para el
        producto anterior."""
        other_product = self.env["product.product"].create(
            {"name": "Otro servicio", "type": "service", "list_price": 55.0}
        )

        order_form = Form(self.env["sale.order"])
        order_form.partner_id = self.partner
        with order_form.order_line.new() as line:
            line.product_id = self.product

        with order_form.order_line.edit(0) as line:
            line.price_unit = 999.0

        with order_form.order_line.edit(0) as line:
            line.product_id = other_product

        order = order_form.save()

        saved_line = order.order_line.filtered(lambda l: l.product_id == other_product)
        self.assertEqual(
            saved_line.price_unit,
            other_product.list_price,
            "Al cambiar de producto debe recalcularse el precio desde la tarifa, "
            "no conservar el precio manual del producto anterior.",
        )
