# models/sale_order.py
from odoo import models, fields, api

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # Add Salesperson to the Line
    salesperson_id = fields.Many2one(
        'res.users', 
        string='Line Salesperson',
        default=lambda self: self.env.user,
        help="The salesperson who will receive commission for this specific line."
    )

    @api.onchange('product_id')
    def _onchange_product_id_set_salesperson(self):
        if not self.salesperson_id and self.order_id.user_id:
            self.salesperson_id = self.order_id.user_id

    @api.model_create_multi
    def create(self, vals_list):
        # Default to the Order Header salesperson if line salesperson is not set
        for vals in vals_list:
            if 'salesperson_id' not in vals and 'order_id' in vals:
                order = self.env['sale.order'].browse(vals['order_id'])
                vals['salesperson_id'] = order.user_id.id
        return super().create(vals_list)

    def _prepare_invoice_line(self, **optional_values):
        # Pass the Line Salesperson to the Invoice Line
        res = super()._prepare_invoice_line(**optional_values)
        res['salesperson_id'] = self.salesperson_id.id
        return res