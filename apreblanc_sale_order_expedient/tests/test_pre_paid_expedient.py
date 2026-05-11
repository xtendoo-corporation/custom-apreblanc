from psycopg2 import IntegrityError

from .common import ExpedientBaseCase


class TestPrePaidExpedient(ExpedientBaseCase):
    def test_create_sets_generated_name_when_default(self):
        record = self.env["pre.paid.expedient"].create(
            {
                "partner_id": self.partner.id,
                "client_id": "C-001",
                "expedient_number": "E-001",
            }
        )

        self.assertTrue(record.name)
        self.assertNotEqual(record.name, "New Pre-paid Expedient")

    def test_unique_client_and_expedient_constraint(self):
        self.env["pre.paid.expedient"].create(
            {
                "partner_id": self.partner.id,
                "client_id": "C-UNIQ",
                "expedient_number": "E-UNIQ",
            }
        )

        with self.assertRaises(IntegrityError):
            with self.cr.savepoint():
                self.env["pre.paid.expedient"].create(
                    {
                        "partner_id": self.partner.id,
                        "client_id": "C-UNIQ",
                        "expedient_number": "E-UNIQ",
                    }
                )

