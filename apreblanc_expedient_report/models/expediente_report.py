from odoo import models, fields, tools


class SaleOrderChatterReport(models.Model):
    _name = "apreblanc.sale.order.chatter.report"
    _description = "Sale Order Chatter Report"
    _auto = False

    message_id = fields.Many2one("mail.message", string="Message")
    date = fields.Datetime(string="Date")
    author_id = fields.Many2one("res.partner", string="Author")
    body = fields.Html(string="Message Body")
    order_id = fields.Many2one("sale.order", string="Sale Order")

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)

        self.env.cr.execute("""
            CREATE VIEW apreblanc_sale_order_chatter_report AS (
                SELECT
                    mm.id AS id,
                    mm.id AS message_id,
                    mm.date AS date,
                    mm.author_id AS author_id,
                    COALESCE(
                        NULLIF(
                            btrim(
                                regexp_replace(
                                    replace(COALESCE(mm.body, ''), '&nbsp;', ' '),
                                    '<[^>]+>',
                                    '',
                                    'g'
                                )
                            ),
                            ''
                        ),
                        tv.tracking_body
                    ) AS body,
                    so.id AS order_id,
                    so.partner_id AS partner_id
                FROM mail_message mm
                JOIN sale_order so ON so.id = mm.res_id
                LEFT JOIN LATERAL (
                    SELECT string_agg(track_line, '<br/>') AS tracking_body
                    FROM (
                        SELECT
                            CASE
                                WHEN mtv.field_id IS NULL THEN NULL
                                ELSE
                                    COALESCE(
                                        NULLIF(mtf.field_description->>'es_ES', ''),
                                        NULLIF(mtf.field_description->>'en_US', ''),
                                        mtf.name::text,
                                        'Campo'
                                    )
                                    || ': '
                                    || COALESCE(
                                        mtv.old_value_char,
                                        mtv.old_value_text,
                                        TO_CHAR(mtv.old_value_datetime, 'YYYY-MM-DD HH24:MI:SS'),
                                        mtv.old_value_float::text,
                                        mtv.old_value_integer::text,
                                        ''
                                    )
                                    || ' → '
                                    || COALESCE(
                                        mtv.new_value_char,
                                        mtv.new_value_text,
                                        TO_CHAR(mtv.new_value_datetime, 'YYYY-MM-DD HH24:MI:SS'),
                                        mtv.new_value_float::text,
                                        mtv.new_value_integer::text,
                                        ''
                                    )
                            END AS track_line
                        FROM mail_tracking_value mtv
                        LEFT JOIN ir_model_fields mtf ON mtf.id = mtv.field_id
                        WHERE mtv.mail_message_id = mm.id
                    ) tracking_lines
                    WHERE track_line IS NOT NULL AND track_line != ''
                ) tv ON TRUE
                WHERE mm.model = 'sale.order'
                  AND so.expedient_type IN ('post_paid', 'pre_paid')
                  AND (
                      NULLIF(
                          btrim(
                              regexp_replace(
                                  replace(COALESCE(mm.body, ''), '&nbsp;', ' '),
                                  '<[^>]+>',
                                  '',
                                  'g'
                              )
                          ),
                          ''
                      ) IS NOT NULL
                      OR tv.tracking_body IS NOT NULL
                  )
            )
        """)
