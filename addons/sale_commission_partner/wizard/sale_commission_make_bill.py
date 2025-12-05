# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import UserError

class SaleCommissionMakeBill(models.TransientModel):
    _name = 'sale.commission.make.bill'
    _description = "Generate Commission Bills"

    date_from = fields.Date("From", required=True, default=lambda self: fields.Date.context_today(self).replace(day=1))
    date_to = fields.Date("To", required=True, default=fields.Date.context_today)
    partner_ids = fields.Many2many('res.partner', string="Agents", help="Leave empty to generate for all agents with commissions.")
    product_id = fields.Many2one('product.product', string="Commission Product", required=True, domain=[('type', '=', 'service')])

    def action_generate_bills(self):
        self.ensure_one()
        
        # 1. Fetch Commission Data
        domain = [
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
        ]
        if self.partner_ids:
            domain.append(('partner_id', 'in', self.partner_ids.ids))
            
        groups = self.env['sale.commission.partner.report']._read_group(
            domain,
            groupby=['partner_id', 'currency_id'],
            aggregates=['commission:sum']
        )

        if not groups:
            raise UserError(_("No commissions found for the selected criteria."))

        moves = self.env['account.move']
        
        # 2. Group by Partner and Currency
        for partner, currency, amount in groups:
            if amount <= 0:
                continue

            # 3. Create Vendor Bill
            move_vals = {
                'move_type': 'in_invoice',
                'partner_id': partner.id,
                'invoice_date': fields.Date.context_today(self),
                'currency_id': currency.id,
                'invoice_line_ids': [
                    (0, 0, {
                        'product_id': self.product_id.id,
                        'name': _("Commission for period %s - %s") % (self.date_from, self.date_to),
                        'quantity': 1,
                        'price_unit': amount,
                    })
                ]
            }
            moves += self.env['account.move'].create(move_vals)

        if not moves:
             raise UserError(_("No bills were generated. Check if commission amounts are positive."))

        return {
            'name': _('Generated Bills'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', moves.ids)],
        }
