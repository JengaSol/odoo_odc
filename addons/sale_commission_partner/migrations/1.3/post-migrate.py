# Part of Odoo. See LICENSE file for full copyright and licensing details.


def migrate(cr, version):
    cr.execute("""
        DELETE FROM sale_commission_plan_partner scpp
         WHERE NOT EXISTS (
             SELECT 1 FROM res_partner rp WHERE rp.id = scpp.partner_id
         )
    """)
