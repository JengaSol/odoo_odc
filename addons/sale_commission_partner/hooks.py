# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command


def post_init_hook(env):
    env['account.move']._backfill_partner_commission_locks()
    for plan in env['sale.commission.plan'].search([('company_id', '!=', False)]):
        if not plan.company_ids:
            plan.company_ids = [Command.set(plan.company_id.ids)]
    env['sale.commission.plan.partner']._cleanup_orphan_records()
