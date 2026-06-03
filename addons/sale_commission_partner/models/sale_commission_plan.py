# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, Command, _
from odoo.exceptions import ValidationError


class SaleCommissionPlan(models.Model):
    _inherit = 'sale.commission.plan'

    user_type = fields.Selection(selection_add=[('partner', "Partner")], ondelete={'partner': 'cascade'})
    partner_ids = fields.One2many('sale.commission.plan.partner', 'plan_id', copy=True)
    company_ids = fields.Many2many(
        'res.company',
        'sale_commission_plan_company_rel',
        'plan_id',
        'company_id',
        string='Companies',
        help="Companies where this commission plan applies.",
    )
    company_id = fields.Many2one(
        compute='_compute_company_id',
        inverse='_inverse_company_id',
        store=True,
        readonly=False,
        required=False,
    )
    currency_id = fields.Many2one(
        compute='_compute_currency_id',
        store=True,
        readonly=False,
    )

    @api.depends('company_ids')
    def _compute_company_id(self):
        for plan in self:
            if len(plan.company_ids) == 1:
                plan.company_id = plan.company_ids
            else:
                plan.company_id = False

    def _inverse_company_id(self):
        for plan in self:
            if plan.company_id:
                plan.company_ids = [Command.set(plan.company_id.ids)]

    @api.depends('company_ids')
    def _compute_currency_id(self):
        for plan in self:
            plan.currency_id = plan.company_ids[:1].currency_id

    @api.constrains('company_ids')
    def _check_company_ids(self):
        for plan in self:
            if not plan.company_ids:
                raise ValidationError(_("A commission plan must apply to at least one company."))

    @api.model
    def default_get(self, field_names):
        res = super().default_get(field_names)
        if 'company_ids' in field_names and not res.get('company_ids') and self.env.company:
            res['company_ids'] = [Command.set(self.env.company.ids)]
        return res

    @api.model
    def _prepare_company_vals(self, vals):
        company_ids = vals.get('company_ids')
        company_id = vals.get('company_id')
        if company_id and not company_ids:
            vals['company_ids'] = [Command.set([company_id])]
        vals.pop('company_id', None)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._prepare_company_vals(vals)
        return super().create(vals_list)

    def write(self, vals):
        if 'company_id' in vals or 'company_ids' in vals:
            vals = dict(vals)
            self._prepare_company_vals(vals)
        return super().write(vals)

    @api.constrains('team_id', 'user_type')
    def _constrains_team_id(self):
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
