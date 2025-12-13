from odoo import models, fields

class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_safaricom_account = fields.Boolean(string='Is Safaricom Account')
    is_safaricom_subscriber = fields.Boolean(string='Is Safaricom Subscriber')
    
    # Store the unique Account or Subscriber number here
    safaricom_number = fields.Char(string='Safaricom Number', index=True, help="Account Number or Subscriber Number")
    
    # Product to use for invoicing this subscriber
    safaricom_service_product_id = fields.Many2one('product.product', string='Service Product')
