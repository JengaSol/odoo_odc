# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Sale Commission Partner',
    'version': '1.0',
    'category': 'Sales/Commission',
    'sequence': 105,
    'summary': "Manage commissions for external partners (Agents)",
    'description': """
    Manage commissions for external partners (Agents).
    - Assign Commission Plans to Partners.
    - Select Agents on Sale Order Lines.
    - Generate Vendor Bills for accrued commissions.
    """,
    'depends': ['sale_commission', 'account'],
    'data': [
        'data/product_data.xml',
        'security/ir.model.access.csv',
        'views/sale_commission_partner_views.xml',
        'views/res_partner_views.xml',
        'views/sale_order_views.xml',
        'report/sale_commission_partner_report.xml',
        'wizard/sale_commission_make_bill_views.xml',
    ],
    'installable': True,
    'license': 'OEEL-1',
}
