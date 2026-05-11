from .common import ExpedientBaseCase


class TestExpedientReturnReason(ExpedientBaseCase):
    def test_create_reason_defaults(self):
        reason = self.env["expedient.return.reason"].create({"name": "R1"})

        self.assertEqual(reason.name, "R1")
        self.assertEqual(reason.sequence, 10)
        self.assertTrue(reason.active)

