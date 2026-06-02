# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class SaleCommissionPartnerMixin(models.AbstractModel):
    _name = 'sale.commission.partner.mixin'
    _description = 'Partner Commission Computation Helpers'

    @api.model
    def _get_partner_plan_partner(self, agent, reference_date):
        if not agent or not reference_date:
            return self.env['sale.commission.plan.partner']
        return self.env['sale.commission.plan.partner'].search([
            ('partner_id', '=', agent.id),
            ('plan_id.active', '=', True),
            ('plan_id.state', '=', 'approved'),
            ('date_from', '<=', reference_date),
            '|',
            ('date_to', '=', False),
            ('date_to', '>=', reference_date),
        ], limit=1)

    @api.model
    def _get_partner_commission_rule(self, plan, product):
        if not plan or not product:
            return self.env['sale.commission.plan.achievement']
        return self.env['sale.commission.plan.achievement'].search([
            ('plan_id', '=', plan.id),
            '|', ('product_id', '=', False), ('product_id', '=', product.id),
            '|', ('product_categ_id', '=', False), ('product_categ_id', '=', product.categ_id.id),
        ], order='product_id DESC, product_categ_id DESC', limit=1)

    @api.model
    def _get_partner_commission_base(self, rule, *, price_subtotal, quantity, purchase_price=0.0, standard_price=0.0):
        if not rule:
            return 0.0
        if rule.type in ('amount_sold', 'amount_invoiced'):
            return price_subtotal
        if rule.type in ('qty_sold', 'qty_invoiced'):
            return quantity
        if rule.type in ('margin', 'margin_invoice_paid'):
            cost = purchase_price * quantity if purchase_price else standard_price * quantity
            return price_subtotal - cost
        return price_subtotal

    @api.model
    def _get_partner_commission_snapshot(self, agent, product, reference_date, *, price_subtotal, quantity, purchase_price=0.0, standard_price=0.0):
        plan_partner = self._get_partner_plan_partner(agent, reference_date)
        if not plan_partner:
            return False
        rule = self._get_partner_commission_rule(plan_partner.plan_id, product)
        if not rule:
            return False
        base = self._get_partner_commission_base(
            rule,
            price_subtotal=price_subtotal,
            quantity=quantity,
            purchase_price=purchase_price,
            standard_price=standard_price,
        )
        rate = rule.rate or 0.0
        return {
            'commission_plan_id': plan_partner.plan_id.id,
            'commission_rule_type': rule.type,
            'commission_rate': rate,
            'commission_base': base,
            'commission_amount': base * rate,
        }
