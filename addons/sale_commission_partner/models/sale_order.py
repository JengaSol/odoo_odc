# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    agent_id = fields.Many2one('res.partner', string="Agent", help="The agent who will receive commission for this order.")

    @api.onchange('agent_id')
    def _onchange_agent_id(self):
        for line in self.order_line:
            line.agent_id = self.agent_id

    def action_confirm(self):
        res = super().action_confirm()
        self.mapped('order_line')._lock_partner_commission_preview()
        return res


class SaleOrderLine(models.Model):
    _inherit = ['sale.order.line', 'sale.commission.partner.mixin']

    agent_id = fields.Many2one('res.partner', string="Agent", help="The agent who will receive commission for this line.")
    commission_plan_id = fields.Many2one(
        'sale.commission.plan',
        string='Commission Plan',
        copy=False,
        readonly=True,
    )
    commission_rule_type = fields.Char(
        string='Commission Rule Type',
        copy=False,
        readonly=True,
    )
    commission_rate = fields.Float(
        string='Commission Rate',
        copy=False,
        readonly=True,
    )
    commission_base = fields.Monetary(
        string='Commission Base',
        currency_field='currency_id',
        copy=False,
        readonly=True,
    )
    commission_amount = fields.Monetary(
        string="Commission Amount",
        currency_field='currency_id',
        compute='_compute_commission_amount',
        store=True,
        readonly=False,
        help="Commission amount for this line. Auto-calculated based on commission plan, but can be manually edited."
    )
    commission_locked = fields.Boolean(
        string='Commission Locked',
        copy=False,
        default=False,
        readonly=True,
    )

    @api.depends('agent_id', 'product_id', 'price_subtotal', 'product_uom_qty', 'purchase_price', 'commission_locked')
    def _compute_commission_amount(self):
        for line in self:
            if line.commission_locked:
                continue
            if not line.agent_id or not line.product_id:
                line.commission_amount = 0.0
                continue

            reference_date = line.order_id.date_order.date() if line.order_id.date_order else fields.Date.context_today(line)
            snapshot = line._get_partner_commission_snapshot(
                line.agent_id,
                line.product_id,
                reference_date,
                price_subtotal=line.price_subtotal,
                quantity=line.product_uom_qty,
                purchase_price=line.purchase_price,
                standard_price=line.product_id.standard_price,
                company=line.company_id,
            )
            line.commission_amount = snapshot['commission_amount'] if snapshot else 0.0

    def _lock_partner_commission_preview(self):
        for line in self.filtered(lambda sol: sol.agent_id and not sol.commission_locked):
            reference_date = line.order_id.date_order.date() if line.order_id.date_order else fields.Date.context_today(line)
            snapshot = line._get_partner_commission_snapshot(
                line.agent_id,
                line.product_id,
                reference_date,
                price_subtotal=line.price_subtotal,
                quantity=line.product_uom_qty,
                purchase_price=line.purchase_price,
                standard_price=line.product_id.standard_price,
                company=line.company_id,
            )
            if not snapshot:
                continue
            snapshot['commission_locked'] = True
            line.write(snapshot)

    def refresh_partner_commission(self, force=False):
        """Recompute partner commission amounts for selected lines."""
        lines = self.filtered(lambda line: line.agent_id and not line.display_type)
        if not lines:
            return 0
        if force:
            lines.write({
                'commission_locked': False,
                'commission_plan_id': False,
                'commission_rule_type': False,
                'commission_rate': 0.0,
                'commission_base': 0.0,
            })
        lines = lines.filtered(lambda line: not line.commission_locked)
        lines._compute_commission_amount()
        if force:
            lines.filtered(lambda line: line.order_id.state == 'sale')._lock_partner_commission_preview()
        return len(lines)

    def _prepare_invoice_line(self, **optional_values):
        res = super()._prepare_invoice_line(**optional_values)
        res['agent_id'] = self.agent_id.id
        return res
