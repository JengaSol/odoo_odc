# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api, fields
from odoo.tools import SQL

class SaleCommissionPartnerReport(models.Model):
    _name = 'sale.commission.partner.report'
    _description = "Partner Commission Report"
    _auto = False
    _order = 'date desc'

    plan_id = fields.Many2one('sale.commission.plan', "Commission Plan", readonly=True)
    partner_id = fields.Many2one('res.partner', "Agent", readonly=True)
    achieved = fields.Monetary("Achieved", readonly=True, currency_field='currency_id')
    commission = fields.Monetary("Commission", readonly=True, currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', "Currency", readonly=True)
    company_id = fields.Many2one('res.company', string='Company', readonly=True)
    date = fields.Date(string="Date", readonly=True)
    source_id = fields.Reference(selection=[('sale.order', 'Sale Order'), ('account.move', 'Invoice'), ('sale.commission.achievement', 'Adjustment')], string="Source", readonly=True)

    payment_state = fields.Selection(selection=[
        ('not_paid', 'Not Paid'),
        ('in_payment', 'In Payment'),
        ('paid', 'Paid'),
        ('partial', 'Partially Paid'),
        ('reversed', 'Reversed'),
        ('invoicing_legacy', 'Invoicing App Legacy'),
    ], string="Payment Status", readonly=True)

    @property
    def _table_query(self):
        return SQL(self._query())

    def _query(self):
        return f"""
            SELECT
                ROW_NUMBER() OVER () AS id,
                sub.plan_id,
                sub.partner_id,
                sub.achieved,
                sub.commission,
                sub.currency_id,
                sub.company_id,
                sub.date,
                sub.source_id,
                sub.payment_state
            FROM (
                {self._query_invoices()}
                UNION ALL
                {self._query_adjustments()}
            ) AS sub
        """

    def _query_invoices(self):
        return f"""
            SELECT
                plan.id AS plan_id,
                aml.agent_id AS partner_id,
                (CASE WHEN move.move_type = 'out_refund' THEN -aml.price_subtotal ELSE aml.price_subtotal END) AS achieved,
                (CASE WHEN move.move_type = 'out_refund' THEN -aml.price_subtotal ELSE aml.price_subtotal END * COALESCE(rule.rate, 0.0)) AS commission,
                move.currency_id AS currency_id,
                move.company_id AS company_id,
                move.date AS date,
                concat('account.move,', move.id) AS source_id,
                move.payment_state AS payment_state
            FROM account_move_line aml
            JOIN account_move move ON aml.move_id = move.id
            JOIN res_partner partner ON aml.agent_id = partner.id
            JOIN sale_commission_plan_partner plan_partner ON plan_partner.partner_id = partner.id
            JOIN sale_commission_plan plan ON plan_partner.plan_id = plan.id
            LEFT JOIN product_product pp ON aml.product_id = pp.id
            LEFT JOIN product_template pt ON pp.product_tmpl_id = pt.id
            LEFT JOIN LATERAL (
                SELECT rate
                FROM sale_commission_plan_achievement rule
                WHERE rule.plan_id = plan.id
                  AND (rule.product_id IS NULL OR rule.product_id = aml.product_id)
                  AND (rule.product_categ_id IS NULL OR rule.product_categ_id = pt.categ_id)
                ORDER BY rule.product_id NULLS LAST, rule.product_categ_id NULLS LAST
                LIMIT 1
            ) rule ON TRUE
            WHERE move.move_type IN ('out_invoice', 'out_refund')
              AND move.state = 'posted'
              AND aml.agent_id IS NOT NULL
              AND move.date BETWEEN plan_partner.date_from AND COALESCE(plan_partner.date_to, '2099-12-31')
        """

    def _query_orders(self):
        return f"""
            SELECT
                plan.id AS plan_id,
                sol.agent_id AS partner_id,
                sol.price_subtotal AS achieved,
                (sol.price_subtotal * COALESCE(rule.rate, 0.0)) AS commission,
                order_head.currency_id AS currency_id,
                order_head.company_id AS company_id,
                order_head.date_order::date AS date,
                concat('sale.order,', order_head.id) AS source_id,
                NULL AS payment_state
            FROM sale_order_line sol
            JOIN sale_order order_head ON sol.order_id = order_head.id
            JOIN res_partner partner ON sol.agent_id = partner.id
            JOIN sale_commission_plan_partner plan_partner ON plan_partner.partner_id = partner.id
            JOIN sale_commission_plan plan ON plan_partner.plan_id = plan.id
            LEFT JOIN product_product pp ON sol.product_id = pp.id
            LEFT JOIN product_template pt ON pp.product_tmpl_id = pt.id
            LEFT JOIN LATERAL (
                SELECT rate
                FROM sale_commission_plan_achievement rule
                WHERE rule.plan_id = plan.id
                  AND (rule.product_id IS NULL OR rule.product_id = sol.product_id)
                  AND (rule.product_categ_id IS NULL OR rule.product_categ_id = pt.categ_id)
                ORDER BY rule.product_id NULLS LAST, rule.product_categ_id NULLS LAST
                LIMIT 1
            ) rule ON TRUE
            WHERE order_head.state = 'sale'
              AND sol.agent_id IS NOT NULL
              AND order_head.date_order::date BETWEEN plan_partner.date_from AND COALESCE(plan_partner.date_to, '2099-12-31')
        """

    def _query_adjustments(self):
        return f"""
            SELECT
                plan.id AS plan_id,
                partner.id AS partner_id,
                0.0 AS achieved,
                CASE 
                    WHEN sca.add_partner_id = plan_partner.id THEN sca.achieved 
                    WHEN sca.reduce_partner_id = plan_partner.id THEN -sca.achieved 
                    ELSE 0.0
                END AS commission,
                sca.currency_id AS currency_id,
                sca.company_id AS company_id,
                sca.date AS date,
                concat('sale.commission.achievement,', sca.id) AS source_id,
                'paid' AS payment_state
            FROM sale_commission_achievement sca
            JOIN sale_commission_plan_partner plan_partner ON (sca.add_partner_id = plan_partner.id OR sca.reduce_partner_id = plan_partner.id)
            JOIN res_partner partner ON plan_partner.partner_id = partner.id
            JOIN sale_commission_plan plan ON plan_partner.plan_id = plan.id
            WHERE sca.add_partner_id IS NOT NULL OR sca.reduce_partner_id IS NOT NULL
        """
