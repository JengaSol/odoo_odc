# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class SaleCommissionAchievementReport(models.Model):
    _inherit = "sale.commission.achievement.report"

    def _get_invoices_rates(self):
        """Add margin_invoice_paid to the list of invoice-based achievement types."""
        return super()._get_invoices_rates() + ['margin_invoice_paid']

    def _get_invoice_rates_product(self):
        """
        Calculate the achievement value for invoice lines.
        
        For margin_invoice_paid type:
        - Calculate margin as: price_subtotal - (cost * quantity)
        - Cost is taken from product's standard_price (current cost)
        - Apply currency conversion
        - Handle credit notes by negating the value
        """
        base_calculation = super()._get_invoice_rates_product()
        
        # Add margin calculation for paid invoices
        # Margin = price_subtotal - (cost * quantity)
        # Note: Invoice lines don't have purchase_price field, so we use product's standard_price
        # This represents the current cost of the product
        # standard_price may be stored as JSONB, so we cast it to numeric
        margin_calculation = """
            + CASE
                WHEN fm.move_type = 'out_invoice' THEN
                    rules.margin_invoice_paid_rate * (
                        aml.price_subtotal - 
                        (COALESCE((pp.standard_price)::numeric, 0) * aml.quantity)
                    ) * cr.rate / fm.invoice_currency_rate
                WHEN fm.move_type = 'out_refund' THEN
                    rules.margin_invoice_paid_rate * (
                        aml.price_subtotal - 
                        (COALESCE((pp.standard_price)::numeric, 0) * aml.quantity)
                    ) * cr.rate / fm.invoice_currency_rate * -1
            END
        """
        
        return base_calculation + margin_calculation

    def _get_filtered_moves_cte(self, users=None, teams=None):
        """
        Override to add payment_state field to the filtered_moves CTE.
        
        The base method doesn't include payment_state, but we need it to filter
        for fully paid invoices in the margin_invoice_paid achievement type.
        """
        # Get the base query
        base_query = super()._get_filtered_moves_cte(users=users, teams=teams)
        
        # Add payment_state to the SELECT clause
        # The base query selects: id, team_id, move_type, state, invoice_currency_rate,
        # company_id, invoice_user_id, date, write_date, partner_id
        # We need to add payment_state after partner_id
        
        modified_query = base_query.replace(
            "partner_id\n              FROM account_move",
            "partner_id,\n                    payment_state\n              FROM account_move"
        )
        
        return modified_query

    def _where_invoices(self):
        """
        Extend the WHERE clause to filter for fully paid invoices.
        
        For margin_invoice_paid achievement type, only include invoices where:
        - payment_state = 'paid' (fully settled)
        - This is checked in the _invoices_lines method via the rules table
        """
        base_where = super()._where_invoices()
        
        # The payment_state filter is applied in the invoice query
        # We don't add it here because it needs to be conditional based on the achievement type
        # The filtering happens in _invoices_lines where we have access to the rules
        
        return base_where

    def _invoices_lines(self, users=None, teams=None):
        """
        Override to add payment_state filter for margin_invoice_paid achievement type.
        
        This method generates the SQL query for invoice-based achievements.
        We need to filter for payment_state = 'paid' only when the achievement type
        is margin_invoice_paid.
        """
        # Get the base query from parent
        base_query, table_name = super()._invoices_lines(users=users, teams=teams)
        
        # Add payment_state filter for margin_invoice_paid type
        # We need to add this condition to both team and user queries
        
        # The challenge is that the base query already has the WHERE clause built
        # We need to inject our additional condition
        # The safest way is to add it to the existing conditions in the WHERE clause
        
        # Find the WHERE clauses in both team and user queries and add payment state condition
        payment_filter = """
      AND (
          (rules.margin_invoice_paid_rate IS NULL OR rules.margin_invoice_paid_rate = 0)
          OR fm.payment_state = 'paid'
      )"""
        
        # Insert the payment filter before the GROUP BY in both queries
        # Team query ends with "GROUP BY fm.id, rules.plan_id, rules.user_id"
        # User query ends with "GROUP BY fm.id, rules.plan_id, rules.user_id"
        
        modified_query = base_query.replace(
            "GROUP BY\n        fm.id,\n        rules.plan_id,\n        rules.user_id",
            f"{payment_filter}\n    GROUP BY\n        fm.id,\n        rules.plan_id,\n        rules.user_id"
        )
        
        return modified_query, table_name
