# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields

class Partner(models.Model):
    _inherit = 'res.partner'

    commission_plan_ids = fields.One2many('sale.commission.plan.partner', 'partner_id', string="Commission Plans")
