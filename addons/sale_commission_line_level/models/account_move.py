# models/account_move.py
from odoo import models, fields, api

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    salesperson_id = fields.Many2one(
        'res.users', 
        string='Line Salesperson',
        store=True
    )

class AccountMove(models.Model):
    _inherit = 'account.move'

    def _post(self, soft=True):
        # Standard posting logic
        res = super()._post(soft=soft)
        return res

    def _get_invoice_payment_state(self):
        # This triggers whenever payment state changes
        res = super()._get_invoice_payment_state()
        # If paid, trigger our custom commission calculation
        if self.payment_state == 'paid':
            self._generate_line_commissions()
        return res

    def _generate_line_commissions(self):
        """
        Custom Logic to generate commissions per line based on Margin.
        This bypasses the header-level commission if a line salesperson is set.
        """
        Commission = self.env['sale.commission'] # Adjust model name based on exact V19 Enterprise name
        
        for invoice in self:
            if invoice.move_type != 'out_invoice':
                continue
            
            for line in invoice.invoice_line_ids:
                if not line.salesperson_id or line.display_type != 'product':
                    continue

                # 1. Get the Plan for this User
                # Assuming plans are linked to Users (standard Odoo 18/19)
                # You might need to adjust 'commission_plan_id' depending on your specific configuration
                emp = line.salesperson_id.employee_id
                if not emp or not emp.commission_plan_id:
                    continue
                
                plan = emp.commission_plan_id

                # 2. Calculate Margin for this line
                # Cost is usually on the line or retrieved via product
                cost = line.product_id.standard_price
                margin = line.price_subtotal - (cost * line.quantity)
                
                if margin <= 0:
                    continue

                # 3. Calculate Commission Amount based on Plan Rate
                # Assuming simple flat rate on margin for this example
                # You would fetch the specific rule from the plan here
                commission_rate = 0.0
                for rule in plan.rule_ids:
                    if rule.type == 'margin': 
                        commission_rate = rule.rate # Percentage (e.g., 10.0)
                        break
                
                if commission_rate == 0:
                    continue

                amount_to_pay = margin * (commission_rate / 100.0)

                # 4. Create the Commission Record
                # This model structure depends on the exact V19 schema, 
                # but this is the standard pattern.
                
                order_id = False
                if line.sale_line_ids:
                    order_id = line.sale_line_ids[0].order_id.id

                Commission.create({
                    'user_id': line.salesperson_id.id,
                    'commission_type': 'margin',
                    'amount': amount_to_pay,
                    'source_document': f"{invoice.name} - {line.product_id.name}",
                    'order_id': order_id,
                    'payment_status': 'approved', # Since invoice is paid
                })