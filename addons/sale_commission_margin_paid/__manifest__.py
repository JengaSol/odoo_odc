# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Sales Commission - Margin on Paid Invoices',
    'version': '1.0',
    'category': 'Sales/Sales',
    'summary': 'Add commission achievement type for margin based on fully paid invoices',
    'description': """
Sales Commission - Margin on Paid Invoices
===========================================

This module extends the sale_commission module to add a new achievement type:
"Margin (Invoices Fully Paid)".

Features:
---------
* Calculate commission based on margin from fully paid invoices only
* Properly handle credit notes (reversals)
* Support currency conversion
* Respect product and category filters from commission plans
* Use product standard_price for margin calculation

The margin is calculated as: price_subtotal - (cost * quantity)
Only invoices with payment_state = 'paid' are included in the calculation.
    """,
    'depends': [
        'sale_commission',
        'sale_commission_margin',
    ],
    'data': [
        'views/achievement_report_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'OEEL-1',
}
