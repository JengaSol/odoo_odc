# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime
from odoo import models, api, fields

class SaleCommissionAchievementReport(models.Model):
    _inherit = 'sale.commission.achievement.report'

    @api.model
    def _get_filtered_orders_cte(self, users=None, teams=None):
        date_from, date_to, company_condition = self._get_achievement_default_dates()
        today = fields.Date.today().strftime('%Y-%m-%d')
        date_from_condition = f"""AND date_order >= '{datetime.strftime(date_from, "%Y-%m-%d")}'""" if date_from else ""
        
        # Modified to include orders where the user is on the lines, even if not on the header
        user_filter = ""
        if users:
            user_ids = ','.join(str(i) for i in users.ids)
            user_filter = f"""
                AND (
                    user_id in ({user_ids})
                    OR EXISTS (
                        SELECT 1 FROM sale_order_line sol 
                        WHERE sol.order_id = sale_order.id 
                        AND sol.salesperson_id in ({user_ids})
                    )
                )
            """

        query = f"""
        filtered_orders AS (
            SELECT
                    id,
                    team_id,
                    state,
                    currency_rate,
                    company_id,
                    user_id,
                    date_order,
                    write_date,
                    partner_id
              FROM sale_order
             WHERE state = 'sale'
               {company_condition}
               {user_filter}
               {'AND team_id in (%s)' % ','.join(str(i) for i in teams.ids) if teams else ''}
               {date_from_condition}
               AND date_order <= '{datetime.strftime(date_to, "%Y-%m-%d") if date_to else today}'
        )
        """
        return query

    @api.model
    def _get_filtered_moves_cte(self, users=None, teams=None):
        date_from, date_to, company_condition = self._get_achievement_default_dates()
        today = fields.Date.today().strftime('%Y-%m-%d')
        date_from_str = date_from and datetime.strftime(date_from, "%Y-%m-%d")
        date_from_condition = f"""AND date >= '{date_from_str}'""" if date_from_str else ""
        
        # Modified to include invoices where the user is on the lines
        user_filter = ""
        if users:
            user_ids = ','.join(str(i) for i in users.ids)
            user_filter = f"""
                AND (
                    invoice_user_id in ({user_ids})
                    OR EXISTS (
                        SELECT 1 FROM account_move_line aml 
                        WHERE aml.move_id = account_move.id 
                        AND aml.salesperson_id in ({user_ids})
                    )
                )
            """

        query = f"""
        filtered_moves AS (
            SELECT
                    id,
                    team_id,
                    move_type,
                    state,
                    invoice_currency_rate,
                    company_id,
                    invoice_user_id,
                    date,
                    write_date,
                    partner_id
              FROM account_move
             WHERE move_type IN ('out_invoice', 'out_refund')
               AND state = 'posted'
               {company_condition}
             {user_filter}
             {'AND team_id in (%s)' % ','.join(str(i) for i in teams.ids) if teams else ''}
               {date_from_condition}
               AND date <= '{datetime.strftime(date_to, "%Y-%m-%d") if date_to else today}'
        )
        """
        return query

    @api.model
    def _sale_lines(self, users=None, teams=None):
        # Override to join on sol.salesperson_id instead of fo.user_id for user-based rules
        return f"""
{self._get_filtered_orders_cte(users=users, teams=teams)},
sale_rules AS (
    SELECT
        COALESCE(scpu.date_from, scp.date_from) AS date_from,
        COALESCE(scpu.date_to, scp.date_to) AS date_to,
        scpu.user_id AS user_id,
        scp.team_id AS team_id,
        scp.id AS plan_id,
        scpa.product_id,
        scpa.product_categ_id,
        scp.company_id,
        {self.env.company.currency_id.id} AS currency_id,
        scp.user_type = 'team' AS team_rule,
        {self._rate_to_case(self._get_sale_rates())}
        {self._select_rules()}
    FROM sale_commission_plan_achievement scpa
    JOIN sale_commission_plan scp ON scp.id = scpa.plan_id
    JOIN sale_commission_plan_user scpu ON scpa.plan_id = scpu.plan_id
    WHERE scp.active
      AND scp.state = 'approved'
      {self._get_company_condition('scp')}
      AND scpa.type IN ({','.join("'%s'" % r for r in self._get_sale_rates())})
    {'AND scpu.user_id in (%s)' % ','.join(str(i) for i in users.ids) if users else ''}
), sale_commission_lines_team AS (
    SELECT
        rules.user_id,
        MAX(rules.team_id),
        rules.plan_id,
        SUM({self._get_sale_rates_product()}) AS achieved,
        {self.env.company.currency_id.id},
        MAX(fo.date_order) AS date,
        MAX(rules.company_id),
        {self._select_sales()}
    FROM sale_rules rules
    {self._join_sales(join_type='team')}
    JOIN product_product pp
      ON sol.product_id = pp.id
    JOIN product_template pt
      ON pp.product_tmpl_id = pt.id
    WHERE rules.team_rule
      AND fo.team_id = rules.team_id
    {'AND fo.team_id in (%s)' % ','.join(str(i) for i in teams.ids) if teams else ''}
    {self._where_sales()}
    GROUP BY
        fo.id,
        rules.plan_id,
        rules.user_id
), sale_commission_lines_user AS (
    SELECT
        rules.user_id,
        MAX(fo.team_id),
        rules.plan_id,
        SUM({self._get_sale_rates_product()}) AS achieved,
        {self.env.company.currency_id.id} AS currency_id,
        MAX(fo.date_order) AS date,
        MAX(rules.company_id),
        {self._select_sales()}
    FROM sale_rules rules
    JOIN filtered_orders fo ON 1=1 -- Cross join, filtered by line match below
    JOIN sale_order_line sol
      ON sol.order_id = fo.id
    JOIN currency_rate cr
      ON cr.company_id=fo.company_id
    JOIN product_product pp
      ON sol.product_id = pp.id
    JOIN product_template pt
      ON pp.product_tmpl_id = pt.id
    WHERE NOT rules.team_rule
      AND sol.salesperson_id = rules.user_id -- CHANGED: Match line salesperson
    {'AND sol.salesperson_id in (%s)' % ','.join(str(i) for i in users.ids) if users else ''}
      {self._where_sales()}
    GROUP BY
        fo.id,
        rules.plan_id,
        rules.user_id
), sale_commission_lines AS (
    (SELECT *, 'sale.order' AS related_res_model FROM sale_commission_lines_team)
    UNION ALL
    (SELECT *, 'sale.order' AS related_res_model FROM sale_commission_lines_user)
)""", 'sale_commission_lines'

    @api.model
    def _invoices_lines(self, users=None, teams=None):
        # Override to join on aml.salesperson_id instead of fm.invoice_user_id for user-based rules
        return f"""
{self._get_filtered_moves_cte(users=users, teams=teams)},
invoice_commission_lines_team AS (
    SELECT
        {self._select_invoices()}
    FROM invoices_rules rules
         {self._join_invoices(join_type='team')}
    WHERE {self._where_invoices()}
      AND rules.team_rule
      AND fm.team_id = rules.team_id
    {'AND fm.team_id in (%s)' % ','.join(str(i) for i in teams.ids) if teams else ''}
      AND fm.date BETWEEN rules.date_from AND rules.date_to
      AND (rules.product_id IS NULL OR rules.product_id = aml.product_id)
      AND (rules.product_categ_id IS NULL OR rules.product_categ_id = pt.categ_id)
    GROUP BY
        fm.id,
        rules.plan_id,
        rules.user_id
), invoice_commission_lines_user AS (
    SELECT
          {self._select_invoices()}
    FROM invoices_rules rules
         JOIN filtered_moves fm ON 1=1 -- Cross join, filtered by line match below
         JOIN account_move_line aml
            ON aml.move_id = fm.id
         LEFT JOIN product_product pp
            ON aml.product_id = pp.id
         LEFT JOIN product_template pt
            ON pp.product_tmpl_id = pt.id
         JOIN currency_rate cr
            ON cr.company_id = fm.company_id
    WHERE {self._where_invoices()}
      AND NOT rules.team_rule
      AND aml.salesperson_id = rules.user_id -- CHANGED: Match line salesperson
    {'AND aml.salesperson_id in (%s)' % ','.join(str(i) for i in users.ids) if users else ''}
      AND fm.date BETWEEN rules.date_from AND rules.date_to
      AND (rules.product_id IS NULL OR rules.product_id = aml.product_id)
      AND (rules.product_categ_id IS NULL OR rules.product_categ_id = pt.categ_id)
    GROUP BY
        fm.id,
        rules.plan_id,
        rules.user_id
), invoice_commission_lines AS (
    (SELECT *, 'account.move' AS related_res_model FROM invoice_commission_lines_team)
    UNION ALL
    (SELECT *, 'account.move' AS related_res_model FROM invoice_commission_lines_user)
)""", 'invoice_commission_lines'

    @api.model
    def _where_invoices(self):
        """
        Override to prevent subscription filtering from parent module.
        
        The sale_commission_subscription module adds a WHERE clause that references
        the 'sub' table, but we don't include that table in our line-level queries.
        This override returns only the base WHERE conditions without subscription filtering.
        """
        return """
          aml.display_type = 'product'
          AND fm.move_type in ('out_invoice', 'out_refund')
          AND fm.state = 'posted'
        """
