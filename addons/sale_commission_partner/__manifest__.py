# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Sale Commission Partner',
    'version': '1.2',
    'category': 'Sales/Commission',
    'sequence': 105,
    'summary': "Manage commissions for external partners (Agents)",
    'description': """
    Manage commissions for external partners (Agents).
    - Assign Commission Plans to Partners.
    - Select Agents on Sale Order Lines.
    - Generate Vendor Bills for accrued commissions.
    """,
    'depends': ['sale_commission', 'sale_commission_margin_paid', 'sale_margin', 'account'],
    'data': [
        'data/product_data.xml',
        'security/ir.model.access.csv',
        'wizard/sale_commission_add_multiple_partner_views.xml',
        'wizard/sale_commission_refresh_views.xml',
        'views/sale_commission_partner_views.xml',
        'views/sale_commission_plan_views.xml',
        'views/sale_commission_achievement_views.xml',
        'views/sale_commission_menus.xml',
        'views/res_partner_views.xml',
        'views/sale_order_views.xml',
        'views/account_move_views.xml',
        'report/sale_commission_partner_report.xml',
        'wizard/sale_commission_make_bill_views.xml',
    ],
    'installable': True,
    'post_init_hook': 'post_init_hook',
    'license': 'OEEL-1',
}
