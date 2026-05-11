from .common import ExpedientBaseCase


class TestSaleReport(ExpedientBaseCase):
    def test_valid_field_parameter_accepts_widget(self):
        report_model = self.env["sale.report"]
        field_obj = report_model._fields["margin_percent"]

        self.assertTrue(report_model._valid_field_parameter(field_obj, "widget"))
        self.assertFalse(report_model._valid_field_parameter(field_obj, "not_a_real_param"))

