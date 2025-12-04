# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import common, tagged
from odoo import fields, Command

@tagged('post_install', '-at_install')
class TestSaleCommissionPartner(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_agent = cls.env['res.partner'].create({'name': 'Agent Smith'})
        cls.partner_customer = cls.env['res.partner'].create({'name': 'Customer Doe'})
        cls.product = cls.env['product.product'].create({
            'name': 'Test Product',
            'list_price': 100.0,
            'standard_price': 50.0,
            'type': 'service',
        })
        cls.commission_product = cls.env['product.product'].create({
            'name': 'Commission Expense',
            'type': 'service',
        })

        # Create Commission Plan
        cls.commission_plan = cls.env['sale.commission.plan'].create({
            'name': 'Agent 10%',
            'user_type': 'partner',
            'company_id': cls.env.company.id,
            'achievement_ids': [Command.create({
                'type': 'amount_sold',
                'rate': 10.0,
            })],
        })
        cls.commission_plan.action_approve()

        # Assign Plan to Agent
        cls.partner_agent.write({
            'commission_plan_ids': [Command.create({
                'plan_id': cls.commission_plan.id,
                'date_from': fields.Date.today(),
            })]
        })

    def test_commission_flow(self):
        # 1. Create Sale Order with Agent
        so = self.env['sale.order'].create({
            'partner_id': self.partner_customer.id,
            'agent_id': self.partner_agent.id,
            'order_line': [Command.create({
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'price_unit': 100.0,
            })],
        })
        
        # Verify Agent propagated to line
        self.assertEqual(so.order_line.agent_id, self.partner_agent)

        # Confirm SO
        so.action_confirm()

        # 2. Check Commission Report (Sale Order based)
        # We need to flush to ensure SQL view sees the data
        self.env.flush_all()
        
        report_lines = self.env['sale.commission.partner.report'].search([
            ('partner_id', '=', self.partner_agent.id),
            ('source_id', 'like', 'sale.order%')
        ])
        self.assertTrue(report_lines, "Should have commission report line for SO")
        self.assertAlmostEqual(report_lines[0].commission, 10.0, msg="Commission should be 10% of 100")

        # 3. Create Invoice
        invoice = so._create_invoices()
        invoice.action_post()

        # 4. Check Commission Report (Invoice based)
        self.env.flush_all()
        report_lines_inv = self.env['sale.commission.partner.report'].search([
            ('partner_id', '=', self.partner_agent.id),
            ('source_id', 'like', 'account.move%')
        ])
        self.assertTrue(report_lines_inv, "Should have commission report line for Invoice")
        self.assertAlmostEqual(report_lines_inv[0].commission, 10.0, msg="Commission should be 10% of 100")

        # 5. Generate Vendor Bill
        wizard = self.env['sale.commission.make.bill'].create({
            'date_from': fields.Date.today(),
            'date_to': fields.Date.today(),
            'partner_ids': [Command.set([self.partner_agent.id])],
            'product_id': self.commission_product.id,
        })
        action = wizard.action_generate_bills()
        
        # Verify Bill Created
        bill_domain = action['domain']
        bills = self.env['account.move'].search(bill_domain)
        self.assertTrue(bills, "Vendor Bill should be generated")
        self.assertEqual(bills.partner_id, self.partner_agent)
        self.assertEqual(bills.move_type, 'in_invoice')
        self.assertAlmostEqual(bills.amount_total, 10.0, msg="Bill amount should be 10.0")

    def test_automatic_bill_generation_on_payment(self):
        """Test that vendor bills are automatically created when invoice is paid."""
        # 1. Create Sale Order with Agent
        so = self.env['sale.order'].create({
            'partner_id': self.partner_customer.id,
            'agent_id': self.partner_agent.id,
            'order_line': [Command.create({
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'price_unit': 100.0,
            })],
        })
        
        so.action_confirm()
        
        # 2. Create and Post Invoice
        invoice = so._create_invoices()
        invoice.action_post()
        
        # Verify no bills exist yet
        bills_before = self.env['account.move'].search([
            ('move_type', '=', 'in_invoice'),
            ('partner_id', '=', self.partner_agent.id)
        ])
        self.assertFalse(bills_before, "No bills should exist before payment")
        
        # 3. Register Payment
        payment_register = self.env['account.payment.register'].with_context(
            active_model='account.move',
            active_ids=invoice.ids
        ).create({
            'payment_date': fields.Date.today(),
        })
        payment_register.action_create_payments()
        
        # 4. Verify Automatic Bill Generation
        bills_after = self.env['account.move'].search([
            ('move_type', '=', 'in_invoice'),
            ('partner_id', '=', self.partner_agent.id)
        ])
        self.assertTrue(bills_after, "Vendor Bill should be automatically generated")
        self.assertEqual(len(bills_after), 1, "Exactly one bill should be created")
        self.assertAlmostEqual(bills_after.amount_total, 5.0, msg="Bill amount should be 5.0 (5% of 100)")
        self.assertIn("Commission for period", bills_after.invoice_line_ids[0].name, "Bill line should have commission period description")

