# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api


class SaleCommissionAchievementReport(models.Model):
    _inherit = 'sale.commission.achievement.report'

    source_name = fields.Char(
        string="Invoice",
        compute='_compute_source_name',
        store=False,
        help="Invoice number related to this achievement"
    )

    invoice_status = fields.Selection([
        ('not_paid', 'Not Paid'),
        ('in_payment', 'In Payment'),
        ('paid', 'Paid'),
        ('partial', 'Partially Paid'),
        ('reversed', 'Reversed'),
        ('invoicing_legacy', 'Invoicing App Legacy'),
    ], string="Invoice Status", compute='_compute_invoice_status', store=False)

    @api.depends('related_res_model', 'related_res_id')
    def _compute_source_name(self):
        """
        Compute the invoice number for the source document.
        
        For sale orders: displays the related invoice name (e.g., INV/2025/0001)
        For invoices: displays the invoice name (e.g., INV/2025/0001)
        For adjustments: displays 'Manual Adjustment'
        """
        for record in self:
            if not record.related_res_model or not record.related_res_id:
                record.source_name = False
                continue
            
            if record.related_res_model == 'sale.order':
                # For sale orders, get the related invoice
                order = self.env['sale.order'].browse(record.related_res_id)
                if order.exists():
                    # Get the first invoice related to this order
                    invoice = order.invoice_ids.filtered(lambda inv: inv.move_type == 'out_invoice')[:1]
                    record.source_name = invoice.name if invoice else order.name
                else:
                    record.source_name = False
            elif record.related_res_model == 'account.move':
                move = self.env['account.move'].browse(record.related_res_id)
                record.source_name = move.name if move.exists() else False
            elif record.related_res_model == 'sale.commission.achievement':
                record.source_name = 'Manual Adjustment'
            else:
                record.source_name = f"{record.related_res_model}/{record.related_res_id}"

    @api.depends('related_res_model', 'related_res_id')
    def _compute_invoice_status(self):
        """
        Compute the payment status of the related invoice.
        
        For sale orders: gets the payment state from the related invoice
        For invoices: gets the payment state directly
        For adjustments: no status
        """
        for record in self:
            if not record.related_res_model or not record.related_res_id:
                record.invoice_status = False
                continue
            
            if record.related_res_model == 'sale.order':
                # For sale orders, get the payment state from the related invoice
                order = self.env['sale.order'].browse(record.related_res_id)
                if order.exists():
                    invoice = order.invoice_ids.filtered(lambda inv: inv.move_type == 'out_invoice')[:1]
                    record.invoice_status = invoice.payment_state if invoice else False
                else:
                    record.invoice_status = False
            elif record.related_res_model == 'account.move':
                move = self.env['account.move'].browse(record.related_res_id)
                record.invoice_status = move.payment_state if move.exists() else False
            else:
                record.invoice_status = False

