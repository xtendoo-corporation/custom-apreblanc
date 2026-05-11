from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class ExpedientBaseCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Cliente Test"})
        cls.study_partner = cls.env["res.partner"].create(
            {
                "name": "Persona Estudio",
                "is_study_entity": True,
            }
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Servicio Test",
                "type": "service",
                "list_price": 100.0,
            }
        )
        cls.return_reason = cls.env["expedient.return.reason"].create(
            {"name": "Falta documentacion"}
        )

    @classmethod
    def _order_line_vals(cls, qty=1.0, price=100.0):
        return [
            (
                0,
                0,
                {
                    "product_id": cls.product.id,
                    "name": "Linea test",
                    "product_uom_qty": qty,
                    "price_unit": price,
                },
            )
        ]

    @classmethod
    def _create_sale_order(cls, **extra_vals):
        vals = {
            "partner_id": cls.partner.id,
            "order_line": cls._order_line_vals(),
        }
        vals.update(extra_vals)
        return cls.env["sale.order"].create(vals)

    @classmethod
    def _create_template(cls, **extra_vals):
        vals = {
            "name": "Plantilla Test",
            "partner_id": cls.partner.id,
        }
        vals.update(extra_vals)
        return cls.env["sale.order.template"].create(vals)

