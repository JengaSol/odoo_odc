# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class SaleCommissionPlanPartner(models.Model):
    _name = 'sale.commission.plan.partner'
    _description = "Commission Plan Partner"
    _order = 'date_from'

    _rec_name = 'name'

    plan_id = fields.Many2one('sale.commission.plan', "Commission Plan", required=True, ondelete='cascade')
    partner_id = fields.Many2one('res.partner', "Partner", required=True, ondelete='cascade')
    date_from = fields.Date("From", default=fields.Date.today, required=True)
    date_to = fields.Date("To")
    name = fields.Char(compute='_compute_name', store=True)

    @api.depends('partner_id', 'plan_id')
    def _compute_name(self):
        for record in self:
            record.name = f"{record.partner_id.name} ({record.plan_id.name})"

    @api.depends('partner_id', 'plan_id')
    def _compute_display_name(self):
        for record in self:
            record.display_name = f"{record.partner_id.name} ({record.plan_id.name})"

    def _check_plan_partner_overlap(self, mode):
        """ Check if the partner is already assigned to a plan for the same period. """
        for plan_partner in self:
            domain = [
                ('partner_id', '=', plan_partner.partner_id.id),
                ('id', '!=', plan_partner.id),
                ('date_from', '<=', plan_partner.date_to or fields.Date.today()),
                '|',
                ('date_to', '=', False),
                ('date_to', '>=', plan_partner.date_from),
            ]
            if self.search_count(domain):
                raise ValidationError(_("The partner is already assigned to a plan for this period."))

    @api.constrains('date_from', 'date_to')
    def _constrains_date(self):
        for plan_partner in self:
            if plan_partner.date_to and plan_partner.date_from > plan_partner.date_to:
                raise ValidationError(_("The start date must be before the end date."))
            plan_partner._check_plan_partner_overlap('date')

    @api.constrains('partner_id', 'plan_id')
    def _constrains_partner_id(self):
        self._check_plan_partner_overlap('partner')
