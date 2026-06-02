# Part of Odoo. See LICENSE file for full copyright and licensing details.


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    env['account.move']._backfill_partner_commission_locks()
