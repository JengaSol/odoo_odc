# Part of Odoo. See LICENSE file for full copyright and licensing details.


def post_init_hook(env):
    env['account.move']._backfill_partner_commission_locks()
