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
        order_label = order.display_name or order.name or order.id
        partner_label = None
        if getattr(order, "partner_id", False):
            partner_label = order.partner_id.display_name or order.partner_id.name or order.partner_id.id
        template_record = (
            getattr(order, "sale_order_template_id", False)
            or getattr(self, "sale_order_template_id", False)
            or getattr(self, "template_id", False)
        )
        template_label = None
        if template_record:
            template_label = template_record.display_name or template_record.name or template_record.id
        if not self.application_rule:
            print(
                "Template line %s (order=%s, partner=%s, template=%s): no application_rule -> True"
                % (self.id, order_label, partner_label, template_label)
            )
            return True

        eval_context = {
            "order": order,
            "record": order,
            "user": self.env.user,
            "context": self.env.context,
            "env": self.env,
        }

        try:
            # Print para ver el valor de person_type
            person_type_value = getattr(order, 'person_type', 'NO EXISTE')
            print(
                "Template line %s (order=%s, partner=%s, template=%s): evaluating rule=%r"
                % (self.id, order_label, partner_label, template_label, self.application_rule)
            )
            print(
                "Template line %s: order.person_type = %r"
                % (self.id, person_type_value)
            )
            result = bool(safe_eval(self.application_rule, eval_context))
            print(
                "Template line %s (order=%s, partner=%s, template=%s): rule result -> %s"
                % (self.id, order_label, partner_label, template_label, result)
            )
            return result
        except Exception as e:
            person_type_value = getattr(order, 'person_type', 'NO EXISTE')
            print(
                "Error evaluating application rule for template line %s (order=%s, partner=%s, template=%s): %s"
                % (self.id, order_label, partner_label, template_label, str(e))
            )
            print(
                "Template line %s: order.person_type at error time = %r"
                % (self.id, person_type_value)
            )
            return False
