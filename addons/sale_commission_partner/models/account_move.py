# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from collections import defaultdict


class AccountMoveLine(models.Model):
    _inherit = ['account.move.line', 'sale.commission.partner.mixin']

    agent_id = fields.Many2one(
        'res.partner',
        string='Agent',
        help="Partner who will receive commission for this line."
    )
    commission_plan_id = fields.Many2one(
        'sale.commission.plan',
        string='Commission Plan',
        copy=False,
        readonly=True,
    )
    commission_rule_type = fields.Char(
        string='Commission Rule Type',
        copy=False,
        readonly=True,
    )
    commission_rate = fields.Float(
        string='Commission Rate',
        copy=False,
        readonly=True,
    )
    commission_base = fields.Monetary(
        string='Commission Base',
        currency_field='currency_id',
        copy=False,
        readonly=True,
    )
    commission_amount = fields.Monetary(
        string='Commission Amount',
        currency_field='currency_id',
        copy=False,
        readonly=True,
    )
    commission_locked = fields.Boolean(
        string='Commission Locked',
        copy=False,
        default=False,
        readonly=True,
    )

    def _get_partner_commission_purchase_price(self):
        self.ensure_one()
        sol = self.sale_line_ids[:1]
        return sol.purchase_price if sol else 0.0

    def _get_partner_commission_snapshot_values(self):
        self.ensure_one()
        if not self.agent_id or self.display_type != 'product' or not self.product_id:
            return False
        reference_date = self.move_id.date or fields.Date.context_today(self)
        product = self.product_id
        return self._get_partner_commission_snapshot(
            self.agent_id,
            product,
            reference_date,
            price_subtotal=self.price_subtotal,
            quantity=self.quantity,
            purchase_price=self._get_partner_commission_purchase_price(),
            standard_price=product.standard_price,
            company=self.company_id,
        )

    def _apply_partner_commission_sign(self, values):
        if self.move_id.move_type != 'out_refund':
            return values
        signed = dict(values)
        signed['commission_base'] = -signed['commission_base']
        signed['commission_amount'] = -signed['commission_amount']
        return signed

    def _lock_partner_commission(self):
        for line in self:
            if line.commission_locked or not line.agent_id or line.display_type != 'product':
                continue
            values = line._get_partner_commission_snapshot_values()
            if not values:
                continue
            values = line._apply_partner_commission_sign(values)
            values['commission_locked'] = True
            line.write(values)


class AccountMove(models.Model):
    _inherit = 'account.move'

    commission_bills_generated = fields.Boolean(
        copy=False,
        default=False,
        readonly=True,
    )

    @api.depends('amount_residual', 'move_type', 'state', 'company_id', 'reconciled_payment_ids.state')
    def _compute_payment_state(self):
        commission_moves = self.filtered(lambda m: m.move_type in ('out_invoice', 'out_refund'))
        old_states = {move.id: move.payment_state for move in commission_moves}
        super()._compute_payment_state()
        newly_paid = commission_moves.filtered(
            lambda m: m.state == 'posted'
            and old_states.get(m.id) != 'paid'
            and m.payment_state == 'paid'
        )
        newly_paid._action_partner_commission_on_paid()

    def _post(self, soft=True):
        res = super()._post(soft=soft)
        self.filtered(
            lambda move: move.move_type in ('out_invoice', 'out_refund') and move.state == 'posted'
        )._lock_partner_commissions_on_post()
        return res

    def _lock_partner_commissions_on_post(self):
        for move in self:
            lines_to_lock = move.invoice_line_ids.filtered(
                lambda line: line.agent_id
                and not line.commission_locked
                and line.display_type == 'product'
            )
            lines_to_lock.filtered(
                lambda line: (line._get_partner_commission_snapshot_values() or {}).get('commission_rule_type') != 'margin_invoice_paid'
            )._lock_partner_commission()

    def _lock_partner_commissions_on_payment(self):
        for move in self.filtered(lambda m: m.payment_state == 'paid'):
            lines_to_lock = move.invoice_line_ids.filtered(
                lambda line: line.agent_id
                and not line.commission_locked
                and line.display_type == 'product'
            )
            lines_to_lock.filtered(
                lambda line: (line._get_partner_commission_snapshot_values() or {}).get('commission_rule_type') == 'margin_invoice_paid'
            )._lock_partner_commission()

    def _action_partner_commission_on_paid(self):
        for move in self:
            move._lock_partner_commissions_on_payment()
            move._generate_commission_bills()

    @api.model
    def _backfill_partner_commission_locks(self, force=False):
        """Snapshot commissions on already posted/paid invoices missing a lock."""
        moves = self.search([
            ('move_type', 'in', ('out_invoice', 'out_refund')),
            ('state', '=', 'posted'),
        ])
        if force:
            lines = moves.invoice_line_ids.filtered(lambda line: line.agent_id and line.display_type == 'product')
            lines.write({
                'commission_locked': False,
                'commission_plan_id': False,
                'commission_rule_type': False,
                'commission_rate': 0.0,
                'commission_base': 0.0,
                'commission_amount': 0.0,
            })
        moves._lock_partner_commissions_on_post()
        moves.filtered(lambda m: m.payment_state == 'paid')._lock_partner_commissions_on_payment()

    def write(self, vals):
        old_payment_states = {move.id: move.payment_state for move in self}
        res = super().write(vals)
        newly_paid = self.filtered(
            lambda m: m.move_type in ('out_invoice', 'out_refund')
            and m.state == 'posted'
            and old_payment_states.get(m.id) != 'paid'
            and m.payment_state == 'paid'
        )
        newly_paid._action_partner_commission_on_paid()
        return res

    def _generate_commission_bills(self):
        """Generate vendor bills for commissions when invoice is paid."""
        self.ensure_one()
        if self.commission_bills_generated:
            return

        commission_product = self.env.ref('sale_commission_partner.product_commission_default', raise_if_not_found=False)
        if not commission_product:
            return

        commissions = self.env['sale.commission.partner.report'].search([
            ('source_id', '=', f'account.move,{self.id}'),
            ('payment_state', '=', 'paid')
        ])
        if not commissions:
            return

        partner_commissions = defaultdict(lambda: {'total': 0.0, 'currency_id': False, 'date_from': False, 'date_to': False})
        for comm in commissions:
            partner_commissions[comm.partner_id]['total'] += comm.commission
            partner_commissions[comm.partner_id]['currency_id'] = comm.currency_id.id
            if not partner_commissions[comm.partner_id]['date_from'] or comm.date < partner_commissions[comm.partner_id]['date_from']:
                partner_commissions[comm.partner_id]['date_from'] = comm.date
            if not partner_commissions[comm.partner_id]['date_to'] or comm.date > partner_commissions[comm.partner_id]['date_to']:
                partner_commissions[comm.partner_id]['date_to'] = comm.date

        bills = self.env['account.move']
        for partner, data in partner_commissions.items():
            if data['total'] <= 0:
                continue
            date_from = data['date_from']
            date_to = data['date_to']
            description = _("Commission for period %s - %s (%s)") % (date_from, date_to, self.name)
            bills += self.env['account.move'].create({
                'move_type': 'in_invoice',
                'partner_id': partner.id,
                'invoice_date': fields.Date.context_today(self),
                'currency_id': data['currency_id'],
                'invoice_line_ids': [
                    (0, 0, {
                        'product_id': commission_product.id,
                        'name': description,
                        'quantity': 1,
                        'price_unit': data['total'],
                    })
                ]
            })

        if bills:
            self.commission_bills_generated = True
