# __manifest__.py
{
    'name': 'Line Level Sales Commissions',
    'version': '19.0.1.0.0',
    'category': 'Sales/Commissions',
    'summary': 'Assign salespersons to specific SO/Invoice lines for margin-based commissions.',
    'description': """
        Allows selecting a Salesperson per Sale Order Line.
        Propagates this selection to Invoice Lines.
        Calculates Commissions based on Line Margins upon full payment.
    """,
    'depends': ['sale_management', 'account', 'sale_commission', 'sale_margin'],
    'data': [
        'views/sale_order_views.xml',
        'views/account_move_views.xml',
    ],
    'license': 'OEEL-1',
    'installable': True,
    'application': False,
}