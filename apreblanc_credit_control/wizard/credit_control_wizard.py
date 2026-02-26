# Copyright 2024 Xtendoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.tools.misc import format_amount, format_date


class CreditControlWizard(models.TransientModel):
    """Wizard transitorio para analizar deuda vencida bajo demanda."""

    _name = "apreblanc.credit.wizard"
    _description = "Asistente de Control de Crédito Apreblanc"

    debt_limit = fields.Monetary(
        string="Límite de deuda vencida",
        currency_field="currency_id",
        help="Solo se muestran clientes cuya deuda vencida supere este importe.",
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Moneda",
        default=lambda self: self.env.company.currency_id,
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Empresa",
        default=lambda self: self.env.company,
    )
    line_ids = fields.One2many(
        comodel_name="apreblanc.credit.wizard.line",
        inverse_name="wizard_id",
        string="Clientes con deuda",
    )
    computed = fields.Boolean(default=False)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if "debt_limit" in fields_list:
            res["debt_limit"] = self.env.company.credit_control_debt_limit
        return res

    def action_compute(self):
        """Calcula la deuda al vuelo y llena las líneas transitorias."""
        self.ensure_one()
        today = fields.Date.today()
        company = self.company_id
        company_currency = self.currency_id

        self.line_ids.unlink()

        move_lines = self.env["account.move.line"].search(
            [
                ("account_id.account_type", "=", "asset_receivable"),
                ("reconciled", "=", False),
                ("move_id.state", "=", "posted"),
                ("move_id.move_type", "in", ["out_invoice", "out_refund"]),
                ("company_id", "=", company.id),
                ("partner_id", "!=", False),
            ]
        )

        partner_data = {}
        for line in move_lines:
            partner = line.partner_id.commercial_partner_id
            if partner.id not in partner_data:
                partner_data[partner.id] = {"overdue": 0.0, "pending": 0.0}

            if line.currency_id and line.currency_id != company_currency:
                amount = line.currency_id._convert(
                    line.amount_residual_currency,
                    company_currency,
                    company,
                    today,
                )
            else:
                amount = line.amount_residual

            if line.date_maturity and line.date_maturity < today:
                partner_data[partner.id]["overdue"] += amount
            else:
                partner_data[partner.id]["pending"] += amount

        WizardLine = self.env["apreblanc.credit.wizard.line"]
        for partner_id, data in partner_data.items():
            if data["overdue"] <= self.debt_limit:
                continue
            WizardLine.create(
                {
                    "wizard_id": self.id,
                    "partner_id": partner_id,
                    "overdue_amount": data["overdue"],
                    "pending_amount": data["pending"],
                    "currency_id": company_currency.id,
                }
            )

        self.computed = True
        return {
            "type": "ir.actions.act_window",
            "res_model": "apreblanc.credit.wizard",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }


class CreditControlWizardLine(models.TransientModel):
    """Línea transitoria: un cliente con su deuda calculada al vuelo."""

    _name = "apreblanc.credit.wizard.line"
    _description = "Línea transitoria de Control de Crédito"

    wizard_id = fields.Many2one(
        comodel_name="apreblanc.credit.wizard",
        string="Wizard",
        required=True,
        ondelete="cascade",
    )
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Cliente",
        required=True,
    )
    overdue_amount = fields.Monetary(
        string="Importe vencido",
        currency_field="currency_id",
    )
    pending_amount = fields.Monetary(
        string="Importe pendiente",
        currency_field="currency_id",
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Moneda",
    )
    email_sent = fields.Boolean(
        string="Email Enviado",
        default=False,
    )

    def action_send_single_email(self):
        """Abre el asistente para previsualizar y editar el email antes de enviarlo."""
        self.ensure_one()
        return {
            "name": _("Previsualizar y Enviar Email"),
            "type": "ir.actions.act_window",
            "res_model": "apreblanc.credit.email.compose",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_line_id": self.id,
            },
        }

    def _prepare_email_content(self, template=None):
        """Construye subject y body HTML completo (plantilla + tablas) sin sanitizar."""
        self.ensure_one()
        partner = self.partner_id.commercial_partner_id
        company = self.wizard_id.company_id
        company_currency = self.wizard_id.currency_id
        today = fields.Date.today()

        move_lines = self.env["account.move.line"].search(
            [
                ("account_id.account_type", "=", "asset_receivable"),
                ("reconciled", "=", False),
                ("move_id.state", "=", "posted"),
                ("move_id.move_type", "in", ["out_invoice", "out_refund"]),
                ("company_id", "=", company.id),
                ("partner_id.commercial_partner_id", "=", partner.id),
            ]
        )

        overdue_lines = []
        pending_lines = []
        overdue_total = 0.0
        pending_total = 0.0

        for ml in move_lines:
            if ml.currency_id and ml.currency_id != company_currency:
                amount = ml.currency_id._convert(
                    ml.amount_residual_currency,
                    company_currency,
                    company,
                    today,
                )
            else:
                amount = ml.amount_residual

            line_data = {
                "name": ml.move_id.name or "",
                "invoice_date": ml.move_id.invoice_date,
                "date_maturity": ml.date_maturity,
                "amount": amount,
            }
            if ml.date_maturity and ml.date_maturity < today:
                overdue_lines.append(line_data)
                overdue_total += amount
            else:
                pending_lines.append(line_data)
                pending_total += amount

        overdue_lines.sort(key=lambda x: x["date_maturity"] or today)
        pending_lines.sort(key=lambda x: x["date_maturity"] or today)

        tables_html = self._build_tables_html(
            overdue_lines, pending_lines, overdue_total, pending_total, company_currency
        )

        # Renderizar la plantilla de email
        if not template:
            template = self.env.ref(
                "apreblanc_credit_control.email_template_apreblanc_credit_control",
                raise_if_not_found=False,
            )
        if template:
            try:
                subject = template._render_template(
                    template.subject, template.model, partner.ids
                ).get(partner.id, "")
                body_rendered = template._render_template(
                    template.body_html, template.model, partner.ids
                ).get(partner.id, "")
            except Exception as e:
                subject = _("Error de plantilla")
                body_rendered = _("<p>Error al renderizar la plantilla: %s</p>") % str(e)
        else:
            subject = _("Recordatorio de facturas pendientes - %s") % partner.name
            body_rendered = (
                '<div style="font-family:Arial,sans-serif;font-size:14px;color:#333;">'
                "<p>Estimado/a <strong>%s</strong>,</p>"
                '<div id="invoice_tables_placeholder"></div>'
                "<p>Atentamente,<br/><strong>%s</strong></p>"
                "</div>"
            ) % (partner.name, self.env.user.name)

        # Insertar las tablas en el placeholder
        placeholder = '<div id="invoice_tables_placeholder"></div>'
        if placeholder in body_rendered:
            body_final = body_rendered.replace(placeholder, tables_html)
        else:
            pos = body_rendered.rfind("</div>")
            if pos != -1:
                body_final = body_rendered[:pos] + tables_html + body_rendered[pos:]
            else:
                body_final = body_rendered + tables_html

        return subject, body_final

    def _build_tables_html(
        self, overdue_lines, pending_lines, overdue_total, pending_total, currency
    ):
        """Genera el HTML de las tablas de facturas."""
        env = self.env

        def fmt_amount(amount):
            return format_amount(env, amount, currency)

        def fmt_date(date):
            return format_date(env, date) if date else ""

        tables_html = ""

        if overdue_lines:
            tables_html += '<h3 style="color:#C0392B;border-bottom:2px solid #C0392B;padding-bottom:4px;">Facturas vencidas</h3>'
            tables_html += '<table style="width:100%;border-collapse:collapse;margin-bottom:16px;">'
            tables_html += '<thead><tr style="background-color:#F8D7DA;color:#721C24;">'
            tables_html += '<th style="border:1px solid #ddd;padding:8px;text-align:left;">Nº Factura</th>'
            tables_html += '<th style="border:1px solid #ddd;padding:8px;text-align:left;">Fecha factura</th>'
            tables_html += '<th style="border:1px solid #ddd;padding:8px;text-align:left;">Fecha vencimiento</th>'
            tables_html += '<th style="border:1px solid #ddd;padding:8px;text-align:right;">Importe</th>'
            tables_html += "</tr></thead><tbody>"
            for line in overdue_lines:
                tables_html += "<tr>"
                tables_html += '<td style="border:1px solid #ddd;padding:8px;">%s</td>' % line["name"]
                tables_html += '<td style="border:1px solid #ddd;padding:8px;">%s</td>' % fmt_date(line["invoice_date"])
                tables_html += '<td style="border:1px solid #ddd;padding:8px;color:#C0392B;font-weight:bold;">%s</td>' % fmt_date(line["date_maturity"])
                tables_html += '<td style="border:1px solid #ddd;padding:8px;text-align:right;">%s</td>' % fmt_amount(line["amount"])
                tables_html += "</tr>"
            tables_html += '</tbody><tfoot><tr style="background-color:#F8D7DA;font-weight:bold;">'
            tables_html += '<td colspan="3" style="border:1px solid #ddd;padding:8px;text-align:right;">TOTAL VENCIDO:</td>'
            tables_html += '<td style="border:1px solid #ddd;padding:8px;text-align:right;">%s</td>' % fmt_amount(overdue_total)
            tables_html += "</tr></tfoot></table>"

        if pending_lines:
            tables_html += '<h3 style="color:#856404;border-bottom:2px solid #856404;padding-bottom:4px;">Facturas pendientes de vencer</h3>'
            tables_html += '<table style="width:100%;border-collapse:collapse;margin-bottom:16px;">'
            tables_html += '<thead><tr style="background-color:#FFF3CD;color:#856404;">'
            tables_html += '<th style="border:1px solid #ddd;padding:8px;text-align:left;">Nº Factura</th>'
            tables_html += '<th style="border:1px solid #ddd;padding:8px;text-align:left;">Fecha factura</th>'
            tables_html += '<th style="border:1px solid #ddd;padding:8px;text-align:left;">Fecha vencimiento</th>'
            tables_html += '<th style="border:1px solid #ddd;padding:8px;text-align:right;">Importe</th>'
            tables_html += "</tr></thead><tbody>"
            for line in pending_lines:
                tables_html += "<tr>"
                tables_html += '<td style="border:1px solid #ddd;padding:8px;">%s</td>' % line["name"]
                tables_html += '<td style="border:1px solid #ddd;padding:8px;">%s</td>' % fmt_date(line["invoice_date"])
                tables_html += '<td style="border:1px solid #ddd;padding:8px;">%s</td>' % fmt_date(line["date_maturity"])
                tables_html += '<td style="border:1px solid #ddd;padding:8px;text-align:right;">%s</td>' % fmt_amount(line["amount"])
                tables_html += "</tr>"
            tables_html += '</tbody><tfoot><tr style="background-color:#FFF3CD;font-weight:bold;">'
            tables_html += '<td colspan="3" style="border:1px solid #ddd;padding:8px;text-align:right;">TOTAL PENDIENTE:</td>'
            tables_html += '<td style="border:1px solid #ddd;padding:8px;text-align:right;">%s</td>' % fmt_amount(pending_total)
            tables_html += "</tr></tfoot></table>"

        return tables_html


class ApreblancCreditEmailCompose(models.TransientModel):
    """Asistente para previsualizar y enviar el email de control de crédito."""

    _name = "apreblanc.credit.email.compose"
    _description = "Redactor de Email de Control de Crédito"

    line_id = fields.Many2one(
        comodel_name="apreblanc.credit.wizard.line",
        string="Línea",
        required=True,
        ondelete="cascade",
    )
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Cliente",
    )
    email_to = fields.Char(string="Destinatario", required=True)
    subject = fields.Char(string="Asunto", required=True)
    template_id = fields.Many2one(
        comodel_name="mail.template",
        string="Plantilla utilizada",
        domain=[("model", "=", "res.partner")],
        default=lambda self: self.env.ref(
            "apreblanc_credit_control.email_template_apreblanc_credit_control", raise_if_not_found=False
        ),
    )
    # body_html construido en Python y almacenado sin sanitizar (readonly en vista)
    body_html = fields.Html(string="Cuerpo HTML", sanitize=False)
    is_send = fields.Boolean(string="Email Enviado", default=False)

    @api.onchange("template_id")
    def _onchange_template_id(self):
        for record in self:
            if record.template_id and record.line_id:
                subject, body = record.line_id._prepare_email_content(template=record.template_id)
                record.subject = subject
                record.body_html = body

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        line_id = res.get("line_id") or self.env.context.get("default_line_id")
        if line_id:
            line = self.env["apreblanc.credit.wizard.line"].browse(line_id)
            if line.exists():
                res["line_id"] = line.id
                res["partner_id"] = line.partner_id.id
                res["email_to"] = line.partner_id.email or ""
                
                template = False
                if res.get("template_id"):
                    template = self.env["mail.template"].browse(res["template_id"])
                    
                subject, body = line._prepare_email_content(template=template)
                res["subject"] = subject
                res["body_html"] = body
        return res

    def action_send_email(self):
        """Envía el email y registra el recordatorio en el historial."""
        self.ensure_one()
        partner = self.partner_id.commercial_partner_id
        wizard_id = self.line_id.wizard_id
        company_currency = wizard_id.currency_id
        body = self.body_html or ""

        # email_from desde la plantilla
        template = self.template_id or self.env.ref(
            "apreblanc_credit_control.email_template_apreblanc_credit_control",
            raise_if_not_found=False,
        )
        email_from = ""
        if template:
            email_from = template._render_template(
                template.email_from, template.model, partner.ids
            ).get(partner.id, "")
        if not email_from:
            email_from = (
                self.env.user.company_id.catchall_formatted
                or self.env.user.email_formatted
            )

        mail_values = {
            "subject": self.subject,
            "body_html": body,
            "body": body,
            "email_to": self.email_to,
            "email_from": email_from,
            "recipient_ids": [(4, partner.id)] if partner else False,
            "auto_delete": False,
            "model": "res.partner",
            "res_id": partner.id,
            "message_type": "email",
        }
        mail = self.env["mail.mail"].create(mail_values)
        mail.send()

        self.env["credit.reminder.history"].create(
            {
                "partner_id": partner.id,
                "date_sent": fields.Datetime.now(),
                "overdue_amount": self.line_id.overdue_amount,
                "pending_amount": self.line_id.pending_amount,
                "currency_id": company_currency.id,
                "user_id": self.env.uid,
                "subject": self.subject,
                "body": body,
                "email_to": self.email_to,
                "state": "sent",
                "email_sent": True,
            }
        )

        self.is_send = True
        self.line_id.email_sent = True

        return {
            "type": "ir.actions.act_window",
            "res_model": "apreblanc.credit.wizard",
            "res_id": wizard_id.id,
            "view_mode": "form",
            "target": "new",
        }
