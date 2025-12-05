# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, Command


class SaleCommissionPlanPartnerWizard(models.TransientModel):
    _name = 'sale.commission.plan.partner.wizard'
    _description = 'Wizard for selecting multiple partners'

    partner_ids = fields.Many2many('res.partner', string="Agents")

    def submit(self):
        plan_id = self.env['sale.commission.plan'].browse(self.env.context.get('active_ids'))
        plan_id.partner_ids = [Command.create({'partner_id': partner_id.id, 'plan_id': plan_id.id}) for partner_id in self.partner_ids]
