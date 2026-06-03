# Part of Odoo. See LICENSE file for full copyright and licensing details.


def migrate(cr, version):
    cr.execute("""
        INSERT INTO sale_commission_plan_company_rel (plan_id, company_id)
        SELECT plan.id, plan.company_id
          FROM sale_commission_plan plan
         WHERE plan.company_id IS NOT NULL
           AND NOT EXISTS (
               SELECT 1
                 FROM sale_commission_plan_company_rel rel
                WHERE rel.plan_id = plan.id
                  AND rel.company_id = plan.company_id
           )
    """)
    cr.execute("""
        UPDATE sale_commission_plan plan
           SET company_id = NULL
         WHERE (
             SELECT COUNT(*)
               FROM sale_commission_plan_company_rel rel
              WHERE rel.plan_id = plan.id
         ) > 1
    """)
