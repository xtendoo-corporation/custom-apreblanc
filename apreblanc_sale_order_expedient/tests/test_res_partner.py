from odoo import fields

from .common import ExpedientBaseCase


class TestResPartner(ExpedientBaseCase):
    def test_study_entity_fields(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Entidad Test",
                "is_study_entity": True,
                "birth_or_registration_date": fields.Date.to_date("2020-01-10"),
            }
        )

        self.assertTrue(partner.is_study_entity)
        self.assertEqual(str(partner.birth_or_registration_date), "2020-01-10")

