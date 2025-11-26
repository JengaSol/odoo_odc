# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class SaleCommissionPlanAchievement(models.Model):
    _inherit = 'sale.commission.plan.achievement'

    type = fields.Selection(
        selection_add=[('margin_invoice_paid', 'Margin (Invoices Fully Paid)')],
        ondelete={'margin_invoice_paid': 'cascade'}
    )
