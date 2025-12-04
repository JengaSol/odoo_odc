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

    def _prepare_invoice_line(self, **optional_values):
        res = super()._prepare_invoice_line(**optional_values)
        res['agent_id'] = self.agent_id.id
        return res
