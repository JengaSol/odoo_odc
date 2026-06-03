# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class SaleCommissionRefreshWizard(models.TransientModel):
    _name = 'sale.commission.refresh.wizard'
    _description = 'Bulk Update Partner Commissions'

    plan_id = fields.Many2one(
        'sale.commission.plan',
        string='Commission Plan',
        domain=[('user_type', '=', 'partner'), ('state', '=', 'approved')],
    )
    order_ids = fields.Many2many(
        'sale.order',
        string='Sales Orders',
        help="Leave empty to update all matching orders in the selected scope.",
    )
    order_state = fields.Selection(
        selection=[
            ('draft', 'Quotations only'),
            ('sale', 'Confirmed orders only'),
            ('all', 'Quotations and confirmed orders'),
        ],
        string='Order Scope',
        default='all',
        required=True,
    )
    date_from = fields.Date(string='From')
    date_to = fields.Date(string='To')
    include_locked = fields.Boolean(
        string='Include confirmed order lines',
        help="Unlock and recalculate commission on confirmed sales order lines, then lock them again.",
    )

    def _get_target_lines(self):
        self.ensure_one()
        line_domain = [('agent_id', '!=', False), ('display_type', '=', False)]
        if self.plan_id:
            agent_ids = self.plan_id.partner_ids.partner_id.ids
            if agent_ids:
                line_domain.append(('agent_id', 'in', agent_ids))
            else:
                return self.env['sale.order.line']
        if self.order_ids:
            line_domain.append(('order_id', 'in', self.order_ids.ids))
        else:
            order_domain = []
            if self.order_state == 'draft':
                order_domain.append(('state', 'in', ['draft', 'sent']))
            elif self.order_state == 'sale':
                order_domain.append(('state', '=', 'sale'))
            else:
                order_domain.append(('state', 'in', ['draft', 'sent', 'sale']))
            if self.date_from:
                order_domain.append(('date_order', '>=', fields.Datetime.to_datetime(self.date_from)))
            if self.date_to:
                order_domain.append(('date_order', '<=', fields.Datetime.end_of(self.date_to, 'day')))
            if order_domain:
                orders = self.env['sale.order'].search(order_domain)
                line_domain.append(('order_id', 'in', orders.ids))
        return self.env['sale.order.line'].search(line_domain)

    def action_refresh(self):
        self.ensure_one()
        lines = self._get_target_lines()
        updated = lines.refresh_partner_commission(force=self.include_locked)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Commissions updated'),
                'message': _('%s sales order line(s) updated.', updated),
                'type': 'success',
                'sticky': False,
            },
        }
