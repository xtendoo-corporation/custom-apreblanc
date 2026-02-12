# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
from odoo.tools.safe_eval import safe_eval
import datetime
import logging

_logger = logging.getLogger(__name__)


class SaleOrderTemplateLine(models.Model):
    _inherit = "sale.order.template.line"

    application_rule = fields.Text(
        string="Application Rule",
        help="Python expression to determine if this line should be applied. "
        "Available variables: 'order' (sale.order), 'user' (res.users), 'datetime' (datetime module).",
    )

    def _should_apply(self, order):
        """Evaluate the application rule against the given order."""
        self.ensure_one()
        if not self.application_rule:
            return True

        eval_context = {
            "order": order,
            "record": order,
            "user": self.env.user,
            "datetime": datetime,
            "context": self.env.context,
            "env": self.env,
        }

        try:
            return bool(safe_eval(self.application_rule, eval_context))
        except Exception as e:
            _logger.error(
                "Error evaluating application rule for template line %s: %s",
                self.id,
                str(e),
            )
            return False
