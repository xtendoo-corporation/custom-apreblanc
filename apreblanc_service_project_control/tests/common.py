from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class ServiceProjectControlBaseCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["res.config.settings"].create({"group_project_task_dependencies": True}).execute()
        cls.partner = cls.env["res.partner"].create({"name": "Cliente servicio test"})
        cls.product_uom_hour = cls.env.ref("uom.product_uom_hour")
        cls.service_product = cls.env["product.product"].create(
            {
                "name": "Servicio controlado",
                "detailed_type": "service",
                "list_price": 150.0,
                "uom_id": cls.product_uom_hour.id,
                "uom_po_id": cls.product_uom_hour.id,
                "apreblanc_target_hours": 2.5,
                "apreblanc_create_service_project": True,
            }
        )
        cls.material_product = cls.env["product.product"].create(
            {
                "name": "Material auxiliar",
                "detailed_type": "consu",
                "list_price": 25.0,
            }
        )
        cls.service_product_no_project = cls.env["product.product"].create(
            {
                "name": "Servicio sin proyecto",
                "detailed_type": "service",
                "list_price": 120.0,
                "uom_id": cls.product_uom_hour.id,
                "uom_po_id": cls.product_uom_hour.id,
                "apreblanc_target_hours": 3.0,
                "apreblanc_create_service_project": False,
            }
        )
        cls.env.user.action_create_employee()

    @classmethod
    def _line_vals(cls, product, qty, price=None, name=None):
        return {
            "product_id": product.id,
            "name": name or product.display_name,
            "product_uom_qty": qty,
            "product_uom": product.uom_id.id,
            "price_unit": price if price is not None else product.list_price,
        }

    @classmethod
    def _create_sale_order(cls, line_dicts):
        return cls.env["sale.order"].create(
            {
                "partner_id": cls.partner.id,
                "partner_invoice_id": cls.partner.id,
                "partner_shipping_id": cls.partner.id,
                "pricelist_id": cls.partner.property_product_pricelist.id,
                "order_line": [
                    (0, 0, {**line_vals, "sequence": index * 10})
                    for index, line_vals in enumerate(line_dicts, start=1)
                ],
            }
        )
