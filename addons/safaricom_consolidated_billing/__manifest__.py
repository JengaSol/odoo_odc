{
    'name': 'Safaricom Consolidated Billing Importer',
    'version': '19.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Import and reconcile Safaricom consolidated billing statements',
    'description': """
        This module allows importing Safaricom consolidated PDF statements.
        It parses the PDF to extract invoice lines per subscriber, payments, and adjustments,
        and facilitates reconciliation with Odoo partners and accounts.
    """,
    'author': 'ODC',
    'depends': ['base', 'account', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'data/product_data.xml',
        'views/menus.xml',
        'views/res_partner_views.xml',
        'views/safaricom_statement_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
