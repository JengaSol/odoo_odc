# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, Command

class SaleCommissionPlan(models.Model):
    _inherit = 'sale.commission.plan'

    user_type = fields.Selection(selection_add=[('partner', "Partner")], ondelete={'partner': 'cascade'})
    partner_ids = fields.One2many('sale.commission.plan.partner', 'plan_id', copy=True)

    @api.constrains('team_id', 'user_type')
    def _constrains_team_id(self):
        # Override to allow no team for partner plans if needed, 
        # but base method only checks if user_type == 'team'.
        # So we might not need to do anything if 'partner' behaves like 'person'.
        super()._constrains_team_id()

    def copy_data(self, default=None):
        vals_list = super().copy_data(default=default)
        return [
            dict(vals, partner_ids=self._extract_past_partners(vals.get('partner_ids', [])))
            for vals in vals_list
        ]

    @staticmethod
    def _extract_past_partners(partner_ids):
        today = fields.Date.today()
        return [p for p in partner_ids if len(p) == 3 and not p[2].get('date_to') or p[2]['date_to'] >= today]

    def action_open_commission(self):
        self.ensure_one()
        if self.user_type == 'partner':
            return {
                "type": "ir.actions.act_window",
                "res_model": "sale.commission.partner.report",
                "name": "Related commissions",
                "views": [[self.env.ref('sale_commission_partner.view_sale_commission_partner_report_tree').id, "list"]],
                "domain": [('plan_id', '=', self.id)],
                "context": {'search_default_plan_id': self.id},
            }
        return super().action_open_commission()
