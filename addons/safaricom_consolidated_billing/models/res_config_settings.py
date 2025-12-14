from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    safaricom_tax_breakdown = fields.Boolean(
        string="Detailed Tax Breakdown",
        config_parameter='safaricom.tax_breakdown',
        default=False,
        help="If checked, Invoice Lines will use Net Amount and apply VAT/Excise taxes separately.\n"
             "If unchecked, Invoice Lines will use the Total (Billed) Amount with no tax lines."
    )
