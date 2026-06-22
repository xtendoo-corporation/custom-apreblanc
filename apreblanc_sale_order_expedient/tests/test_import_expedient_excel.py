import base64
from datetime import datetime
from unittest.mock import patch

from odoo.modules.module import get_module_resource

from ..wizards.import_expedient_excel import ImportedExcelSheet
from .common import ExpedientBaseCase


class TestImportExpedientExcel(ExpedientBaseCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.analyst_user = cls.env["res.users"].search(
            [("login", "=", "aaron_import_test")],
            limit=1,
        )
        if not cls.analyst_user:
            cls.analyst_user = (
                cls.env["res.users"]
                .with_context(no_reset_password=True)
                .create(
                    {
                        "name": "Aaron",
                        "login": "aaron_import_test",
                        "groups_id": [(6, 0, [cls.env.ref("base.group_user").id])],
                    }
                )
            )

    def _create_wizard(self, file_content=b"dummy", expedient_type="pre_paid"):
        return self.env["import.expedient.excel"].create(
            {
                "partner_id": self.partner.id,
                "expedient_type": expedient_type,
                "excel_file": base64.b64encode(file_content),
                "file_name": "import.xls",
            }
        )

    def test_load_excel_sheet_supports_xlsb_with_xls_extension(self):
        file_path = get_module_resource(
            "apreblanc_sale_order_expedient", "data", "solvia_caixa_pre.xls"
        )
        with open(file_path, "rb") as excel_file:
            excel_data = excel_file.read()

        wizard = self._create_wizard(excel_data)
        sheet = wizard._load_excel_sheet(excel_data)

        self.assertEqual(sheet.source_format, "xlsb")
        self.assertEqual(sheet.cell_value(0, 5), "ID Oferta")
        self.assertEqual(sheet.cell_value(1, 5), "P-314008")
        self.assertEqual(sheet.cell_value(1, 6), "C2-02173-0006")

    def test_action_import_maps_new_excel_columns(self):
        wizard = self._create_wizard()
        rows = [
            [
                "Analista",
                "Cliente",
                "CARTERA",
                "PF/PJ",
                "Simple/ Compleja",
                "ID Oferta",
                "MACRO",
                "Devoluciones",
                "Fecha de recepción",
                "Fecha de análisis",
                "ESTADO",
                "Fecha cierre Escritura",
            ],
            [
                "Aaron",
                "VICTOR CARRASCOSA REY CONSTRUCCIONES SL",
                "SUBCARTERA TEST IMPORT",
                "PJ",
                "Simple",
                "P-TEST-IMPORT",
                "C2-TEST-0001",
                1.0,
                46024.0,
                46024.0,
                "Autorizada",
                46034.0,
            ],
        ]

        with patch.object(
            type(wizard),
            "_load_excel_sheet",
            return_value=ImportedExcelSheet(
                rows,
                lambda value: (
                    datetime(2026, 1, 1)
                    if int(value) == 46024
                    else datetime(2026, 1, 11)
                ),
                "xlsb",
            ),
        ), patch.object(type(self.env.cr), "commit", return_value=None):
            wizard.action_import_excel()

        order = self.env["sale.order"].search(
            [
                ("client_id", "=", "P-TEST-IMPORT"),
                ("expedient_number", "=", "C2-TEST-0001"),
            ],
            limit=1,
        )

        self.assertTrue(order)
        self.assertEqual(order.partner_id, self.partner)
        self.assertEqual(order.sub_cartera_id.name, "SUBCARTERA TEST IMPORT")
        self.assertEqual(order.expedient_manager_id, self.analyst_user)
        self.assertEqual(order.person_type, "juridica")
        self.assertEqual(order.expedient_difficulty, "simple")
        self.assertEqual(order.deadline, "more")
        self.assertEqual(order.expedient_state, "creada")
        self.assertEqual(str(order.date_reception), "2026-01-01")
        self.assertEqual(order.person_under_study_id.name, "VICTOR CARRASCOSA REY CONSTRUCCIONES SL")
        self.assertTrue(order.expedient_date_end)
