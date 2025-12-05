# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields

class SaleCommissionAchievement(models.Model):
    _inherit = 'sale.commission.achievement'

    add_partner_id = fields.Many2one('sale.commission.plan.partner', "Add to (Agent)", domain=[('plan_id.active', '=', True)])
    reduce_partner_id = fields.Many2one('sale.commission.plan.partner', "Reduce From (Agent)", domain=[('plan_id.active', '=', True)])
