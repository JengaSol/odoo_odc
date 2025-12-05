# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from collections import defaultdict

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    agent_id = fields.Many2one(
        'res.partner',
        string='Agent',
        help="Partner who will receive commission for this line."
    )

class AccountMove(models.Model):
    _inherit = 'account.move'

    def write(self, vals):
        """Trigger vendor bill generation when invoice becomes fully paid."""
        # Store old payment states before write
        old_payment_states = {move.id: move.payment_state for move in self}
        
        res = super().write(vals)
        
        # Check if payment_state changed to 'paid'
        for move in self:
            if move.move_type in ('out_invoice', 'out_refund') and move.state == 'posted':
                old_state = old_payment_states.get(move.id)
                if old_state and old_state != 'paid' and move.payment_state == 'paid':
                    move._generate_commission_bills()
        
        return res

    def _generate_commission_bills(self):
        """Generate vendor bills for commissions when invoice is paid."""
        self.ensure_one()
        
        # Get commission product
        commission_product = self.env.ref('sale_commission_partner.product_commission_default', raise_if_not_found=False)
        if not commission_product:
            return
        
        # Query commission report for this invoice
        commissions = self.env['sale.commission.partner.report'].search([
            ('source_id', '=', f'account.move,{self.id}'),
            ('payment_state', '=', 'paid')
        ])
        
        if not commissions:
            return
        
        # Group by partner
        partner_commissions = defaultdict(lambda: {'total': 0.0, 'currency_id': False, 'date_from': False, 'date_to': False})
        for comm in commissions:
            partner_commissions[comm.partner_id]['total'] += comm.commission
            partner_commissions[comm.partner_id]['currency_id'] = comm.currency_id.id
            if not partner_commissions[comm.partner_id]['date_from'] or comm.date < partner_commissions[comm.partner_id]['date_from']:
                partner_commissions[comm.partner_id]['date_from'] = comm.date
            if not partner_commissions[comm.partner_id]['date_to'] or comm.date > partner_commissions[comm.partner_id]['date_to']:
                partner_commissions[comm.partner_id]['date_to'] = comm.date
        
        # Create vendor bills
        for partner, data in partner_commissions.items():
            if data['total'] <= 0:
                continue
            
            date_from = data['date_from']
            date_to = data['date_to']
            description = _("Commission for period %s - %s (%s)") % (date_from, date_to, self.name)
            
            self.env['account.move'].create({
                'move_type': 'in_invoice',
                'partner_id': partner.id,
                'invoice_date': fields.Date.context_today(self),
                'currency_id': data['currency_id'],
                'invoice_line_ids': [
                    (0, 0, {
                        'product_id': commission_product.id,
                        'name': description,
                        'quantity': 1,
                        'price_unit': data['total'],
                    })
                ]
            })
