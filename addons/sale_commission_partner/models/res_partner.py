# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields

class Partner(models.Model):
    _inherit = 'res.partner'

    commission_plan_ids = fields.One2many('sale.commission.plan.partner', 'partner_id', string="Commission Plans")

    def action_view_commissions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "sale.commission.partner.report",
            "name": "Commissions",
            "views": [[self.env.ref('sale_commission_partner.view_sale_commission_partner_report_tree').id, "list"]],
            "domain": [('partner_id', '=', self.id)],
            "context": {'search_default_partner_id': self.id},
        }
