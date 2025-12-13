# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    agent_id = fields.Many2one('res.partner', string="Agent", help="The agent who will receive commission for this order.")

    @api.onchange('agent_id')
    def _onchange_agent_id(self):
        for line in self.order_line:
            line.agent_id = self.agent_id

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    agent_id = fields.Many2one('res.partner', string="Agent", help="The agent who will receive commission for this line.")
    commission_amount = fields.Monetary(
        string="Commission Amount",
        currency_field='currency_id',
        compute='_compute_commission_amount',
        store=True,
        readonly=False,
        help="Commission amount for this line. Auto-calculated based on commission plan, but can be manually edited."
    )

    @api.depends('agent_id', 'product_id', 'price_subtotal', 'product_uom_qty', 'purchase_price')
    def _compute_commission_amount(self):
        for line in self:
            if not line.agent_id or not line.product_id:
                line.commission_amount = 0.0
                continue
            
            # Find active commission plan for this agent
            plan_partner = self.env['sale.commission.plan.partner'].search([
                ('partner_id', '=', line.agent_id.id),
                ('plan_id.active', '=', True),
                ('date_from', '<=', line.order_id.date_order or fields.Date.today()),
                '|',
                ('date_to', '=', False),
                ('date_to', '>=', line.order_id.date_order or fields.Date.today())
            ], limit=1)
            
            if not plan_partner:
                line.commission_amount = 0.0
                continue
            
            # Find matching commission rule
            rule = self.env['sale.commission.plan.achievement'].search([
                ('plan_id', '=', plan_partner.plan_id.id),
                '|', ('product_id', '=', False), ('product_id', '=', line.product_id.id),
                '|', ('product_categ_id', '=', False), ('product_categ_id', '=', line.product_id.categ_id.id)
            ], order='product_id DESC, product_categ_id DESC', limit=1)
            
            if not rule:
                line.commission_amount = 0.0
                continue
            
            # Calculate commission based on type
            # For sale orders, we always show the EXPECTED commission amount
            # even if actual earning happens later (e.g., on invoice or payment)
            commission_base = 0.0
            
            if rule.type in ('amount_sold', 'amount_invoiced'):
                # Based on sale order/invoice amount
                # Both use price_subtotal for sale orders (expected amount)
                commission_base = line.price_subtotal
            elif rule.type in ('qty_sold', 'qty_invoiced'):
                # Based on quantity
                # Both use ordered quantity for sale orders (expected quantity)
                commission_base = line.product_uom_qty
            elif rule.type in ('margin', 'margin_invoice_paid'):
                # Based on margin (price_subtotal - cost)
                # Show expected margin commission on sale order
                # For margin_invoice_paid, actual earning happens when invoice is paid
                cost = line.purchase_price * line.product_uom_qty
                commission_base = line.price_subtotal - cost
            else:
                # Fallback for any other commission types
                # Default to amount-based calculation
                commission_base = line.price_subtotal
            
            line.commission_amount = commission_base * (rule.rate or 0.0)

    def _prepare_invoice_line(self, **optional_values):
        res = super()._prepare_invoice_line(**optional_values)
        res['agent_id'] = self.agent_id.id
        return res

