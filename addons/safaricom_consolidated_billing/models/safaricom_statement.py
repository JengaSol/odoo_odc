from odoo import models, fields, api, _
from odoo.exceptions import UserError
import base64
import io
import re
from datetime import datetime

# Try importing pypdf, handle if not present
try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

class SafaricomStatement(models.Model):
    _name = 'safaricom.statement'
    _description = 'Safaricom Consolidated Statement'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'statement_date desc, id desc'

    name = fields.Char(string='Statement Reference', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    
    # Changed to res.partner
    partner_id = fields.Many2one('res.partner', string='Main Account (Partner)', required=True, tracking=True, domain=[('is_safaricom_account', '=', True)])
    
    statement_date = fields.Date(string='Statement Date', required=True, tracking=True)
    due_date = fields.Date(string='Due Date')
    
    total_amount_due = fields.Monetary(string='Total Amount Due', currency_field='currency_id', tracking=True)
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    
    pdf_file = fields.Binary(string='PDF Statement', attachment=True, required=True)
    pdf_filename = fields.Char(string='PDF Filename')
    text_content = fields.Text(string='Extracted Text', readonly=True, help="Raw text extracted from PDF for debugging")
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('imported', 'Imported'),
        ('posted', 'Posted'),
        ('cancel', 'Cancelled')
    ], string='Status', default='draft', tracking=True)
    
    invoice_line_ids = fields.One2many('safaricom.invoice.line', 'statement_id', string='Invoice Lines')
    payment_ids = fields.One2many('safaricom.payment', 'statement_id', string='Payments')
    adjustment_ids = fields.One2many('safaricom.adjustment', 'statement_id', string='Adjustments')

    def action_import_pdf(self):
        self.ensure_one()
        if not self.pdf_file:
            raise UserError(_("Please upload a PDF file first."))
        
        if not PdfReader:
            raise UserError(_("pypdf library is missing. Please install it (pip install pypdf)."))

        # Basic structure to hold extracted data
        extracted_text = self._extract_text_from_pdf()
        self.text_content = extracted_text
        self._parse_extracted_text(extracted_text)
        
        self.state = 'imported'

    def _extract_text_from_pdf(self):
        """Extracts text content from the uploaded PDF."""
        try:
            stream = io.BytesIO(base64.b64decode(self.pdf_file))
            reader = PdfReader(stream)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text
        except Exception as e:
            raise UserError(_("Error reading PDF: %s") % str(e))

    def _parse_extracted_text(self, text):
        self.ensure_one()
        # Regex Patterns

        # Invoice Summary: Name | Subscriber | Invoice | Net | VAT | Excise | Total
        # e.g., ODC 5G 100Mbps 795096893 B1-40022733102 3,748.12 689.66 562.22 5,000.00
        # Be careful with Names having spaces.
        # We look for the ending sequence of 4 amounts + Invoice + Subscriber
        invoice_summary_pattern = re.compile(
            r"(?P<name>.+?)\s+(?P<sub_no>\d+)\s+(?P<inv_no>B\d+-\d+)\s+(?P<net>[\d,.-]+)\s+(?P<vat>[\d,.-]+)\s+(?P<excise>[\d,.-]+)\s+(?P<total>[\d,.-]+)$",
            re.MULTILINE
        )

        # Payment/Adjustment Pattern
        # 24/11/2025 P1-... TKO... PYT:-130,000.00
        # Date | Ref1 | Ref2 | Type:Amount
        transaction_pattern = re.compile(
            r"(?P<date>\d{2}/\d{2}/\d{4})\s+(?P<ref1>\S+)\s+(?P<ref2>\S+)\s+(?P<type>PYT|ADJ|INV|TRF):(?P<amount>[\d,.-]+)",
            re.MULTILINE
        )

        # 1. Parse Invoice Summaries
        invoices = []
        # Clear existing lines if re-importing? For now, we append/create, maybe we should unlink old ones if draft?
        self.invoice_line_ids.unlink()
        self.payment_ids.unlink()
        self.adjustment_ids.unlink()

        for match in invoice_summary_pattern.finditer(text):
            data = match.groupdict()
            
            # Find or Create Subscriber Partner
            sub_no = data['sub_no']
            partner = self.env['res.partner'].search([('safaricom_number', '=', sub_no)], limit=1)
            
            # If not found by Safaricom Number, maybe search by Name? (Optional, risky)
            if not partner:
                # Create new Partner matching requested format: "706172689 - 5G 10Mbps"
                partner_name = f"{sub_no} - {data['name'].strip()}"
                partner = self.env['res.partner'].create({
                    'name': partner_name,
                    'safaricom_number': sub_no,
                    'is_safaricom_subscriber': True,
                    'parent_id': self.partner_id.id, # Link to main account partner? Optional
                })
            
            invoices.append({
                'statement_id': self.id,
                'partner_id': partner.id,
                'subscriber_number': sub_no,
                'invoice_number': data['inv_no'],
                'description': data['name'].strip(),
                'period': self.statement_date.strftime('%Y-%m') if self.statement_date else '', # Approximate
                'net_amount': self._parse_money(data['net']),
                'vat_amount': self._parse_money(data['vat']),
                'excise_amount': self._parse_money(data['excise']),
                'amount': self._parse_money(data['total']),
            })
        
        # Batch create invoice lines
        if invoices:
            self.env['safaricom.invoice.line'].create(invoices)


        # 2. Parse Payments and Adjustments
        payments = []
        adjustments = []
        
        for match in transaction_pattern.finditer(text):
            data = match.groupdict()
            try:
                trans_date = datetime.strptime(data['date'], '%d/%m/%Y').date()
            except ValueError:
                continue # Skip invalid dates
            
            amount = self._parse_money(data['amount'])
            
            if data['type'] == 'PYT':
                payments.append({
                    'statement_id': self.id,
                    'date': trans_date,
                    'reference': f"{data['ref1']} / {data['ref2']}",
                    'amount': amount * -1, # Payments are negative in the bill
                })
            elif data['type'] in ['ADJ', 'TRF']:
                adjustments.append({
                    'statement_id': self.id,
                    'date': trans_date,
                    'reference': f"{data['ref1']} / {data['ref2']}",
                    'description': f"Adjustment ({data['type']})",
                    'amount': amount,
                })
        
        if payments:
            self.env['safaricom.payment'].create(payments)
        if adjustments:
            self.env['safaricom.adjustment'].create(adjustments)

    def _parse_money(self, amount_str):
        if not amount_str:
            return 0.0
        return float(amount_str.replace(',', ''))

    def action_post_statement(self):
        """
        Finalize import and create Odoo Invoices for each Partner.
        """
        self.ensure_one()
        
        # Group lines by Partner
        lines_by_partner = {}
        for line in self.invoice_line_ids:
            if not line.partner_id:
                raise UserError(_("Line for %s has no linked Partner. Please fix before posting.") % line.subscriber_number)
            
            if line.partner_id not in lines_by_partner:
                lines_by_partner[line.partner_id] = []
            lines_by_partner[line.partner_id].append(line)
            
        move_vals_list = []
        
        # Get Safaricom Taxes
        safaricom_taxes = self._get_safaricom_taxes()
        
        # Prepare Invoice Data
        for partner, lines in lines_by_partner.items():
            invoice_lines = []
            for line in lines:
                # Determine product to use: Partner specific > Standard 'Subscription' > Fallback
                product = partner.safaricom_service_product_id
                if not product:
                    product = self.env['product.product'].search([('name', '=', 'Subscription')], limit=1)
                
                # If still no product found, we can create a text-based line or specific product
                line_val = {
                    'name': f"{line.description} ({line.invoice_number})",
                    'quantity': 1,
                    'price_unit': line.net_amount, 
                    'tax_ids': [(6, 0, safaricom_taxes.ids)],
                }
                if product:
                    line_val['product_id'] = product.id
                
                invoice_lines.append((0, 0, line_val))
                
            move_vals = {
                'partner_id': partner.id,
                'move_type': 'out_invoice',
                'invoice_date': self.statement_date,
                'invoice_line_ids': invoice_lines,
                'ref': f"Safaricom Statement {self.name}",
            }
            move_vals_list.append(move_vals)
        
        # Create Invoices
        if move_vals_list:
            moves = self.env['account.move'].create(move_vals_list)
            
            # Post invoices if desired? Or leave as Draft? 
            # Usually Draft is safer for review.
            
            # Link back to lines
            # This is tricky because we created bulk invoices. 
            # We can iterate and link if we want, but complexity increases.
            pass

        self.state = 'posted'

    def _get_safaricom_taxes(self):
        """
        Finds or creates VAT 18.4% and Excise 15%.
        """
        Tax = self.env['account.tax']
        taxes = Tax.browse()
        
        # 1. VAT 18.4%
        vat_tax = Tax.search([('name', '=', 'VAT 18.4%'), ('type_tax_use', '=', 'sale'), ('company_id', '=', self.env.company.id)], limit=1)
        if not vat_tax:
            # Try to find a tax group, or create one? 
            # Usually standard Odoo has Tax Groups. We'll rely on default or first found if needed, or simple string.
            # Odoo 17+ uses tax_group_id. 
            # We will use a fallback logic for tax group.
            tax_group = self.env['account.tax.group'].search([('name', 'ilike', 'VAT')], limit=1)
            if not tax_group:
                 tax_group = self.env['account.tax.group'].search([], limit=1)
                 
            vat_tax = Tax.create({
                'name': 'VAT 18.4%',
                'amount': 18.4,
                'amount_type': 'percent',
                'type_tax_use': 'sale',
                'tax_group_id': tax_group.id,
                'company_id': self.env.company.id,
            })
        taxes += vat_tax
        
        # 2. Excise 15%
        excise_tax = Tax.search([('name', '=', 'Excise Duty 15%'), ('type_tax_use', '=', 'sale'), ('company_id', '=', self.env.company.id)], limit=1)
        if not excise_tax:
            tax_group = self.env['account.tax.group'].search([('name', 'ilike', 'Excise')], limit=1)
            if not tax_group:
                 # Fallback to VAT group or any
                 tax_group = self.env['account.tax.group'].search([], limit=1)
            
            excise_tax = Tax.create({
                'name': 'Excise Duty 15%',
                'amount': 15.0,
                'amount_type': 'percent',
                'type_tax_use': 'sale',
                'tax_group_id': tax_group.id,
                'company_id': self.env.company.id,
            })
        taxes += excise_tax
        
        return taxes


class SafaricomInvoiceLine(models.Model):
    _name = 'safaricom.invoice.line'
    _description = 'Extracted Invoice Line'

    statement_id = fields.Many2one('safaricom.statement', string='Statement', ondelete='cascade')
    
    # Changed to res.partner
    partner_id = fields.Many2one('res.partner', string='Subscriber (Partner)')
    subscriber_number = fields.Char(string='Subscriber No (Raw)')
    
    invoice_number = fields.Char(string='Invoice Number')
    period = fields.Char(string='Billing Period')
    
    amount = fields.Monetary(string='Total Amount', currency_field='currency_id')
    net_amount = fields.Monetary(string='Net Amount', currency_field='currency_id')
    vat_amount = fields.Monetary(string='VAT Amount', currency_field='currency_id')
    excise_amount = fields.Monetary(string='Excise Amount', currency_field='currency_id')

    currency_id = fields.Many2one('res.currency', related='statement_id.currency_id', readonly=True)
    
    description = fields.Char(string='Description')

    odoo_invoice_id = fields.Many2one('account.move', string='Created Invoice')


class SafaricomPayment(models.Model):
    _name = 'safaricom.payment'
    _description = 'Extracted Payment'

    statement_id = fields.Many2one('safaricom.statement', string='Statement', ondelete='cascade')
    date = fields.Date(string='Date')
    reference = fields.Char(string='Reference')
    amount = fields.Monetary(string='Amount', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', related='statement_id.currency_id', readonly=True)
    
    odoo_payment_id = fields.Many2one('account.payment', string='Linked Payment')


class SafaricomAdjustment(models.Model):
    _name = 'safaricom.adjustment'
    _description = 'Extracted Adjustment'

    statement_id = fields.Many2one('safaricom.statement', string='Statement', ondelete='cascade')
    date = fields.Date(string='Date')
    reference = fields.Char(string='Reference')
    amount = fields.Monetary(string='Amount', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', related='statement_id.currency_id', readonly=True)
    description = fields.Char(string='Description')

