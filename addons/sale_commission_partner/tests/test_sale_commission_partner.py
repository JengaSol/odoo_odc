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
                'rate': 0.10,
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
        self.assertAlmostEqual(bills_after.amount_total, 10.0, msg="Bill amount should be 10.0 (10% of 100)")
        self.assertIn("Commission for period", bills_after.invoice_line_ids[0].name, "Bill line should have commission period description")

    def test_margin_invoice_paid_commission_on_invoice(self):
        """Commission on paid invoices must use margin, not subtotal."""
        margin_plan = self.env['sale.commission.plan'].create({
            'name': 'Agent 5% margin paid',
            'user_type': 'partner',
            'company_id': self.env.company.id,
            'achievement_ids': [Command.create({
                'type': 'margin_invoice_paid',
                'rate': 0.05,
            })],
        })
        margin_plan.action_approve()
        self.partner_agent.write({
            'commission_plan_ids': [Command.create({
                'plan_id': margin_plan.id,
                'date_from': fields.Date.today(),
            })]
        })

        product = self.env['product.product'].create({
            'name': 'Margin Product',
            'list_price': 10.0,
            'standard_price': 5.0,
            'type': 'service',
        })
        so = self.env['sale.order'].create({
            'partner_id': self.partner_customer.id,
            'agent_id': self.partner_agent.id,
            'order_line': [Command.create({
                'product_id': product.id,
                'product_uom_qty': 1,
                'price_unit': 10.0,
            })],
        })
        so.action_confirm()
        self.assertAlmostEqual(so.order_line.commission_amount, 0.25)

        invoice = so._create_invoices()
        invoice.action_post()
        self.env.flush_all()

        report_unpaid = self.env['sale.commission.partner.report'].search([
            ('partner_id', '=', self.partner_agent.id),
            ('source_id', '=', f'account.move,{invoice.id}'),
        ])
        self.assertFalse(report_unpaid, "Unpaid invoice should not appear for margin_invoice_paid")

        payment_register = self.env['account.payment.register'].with_context(
            active_model='account.move',
            active_ids=invoice.ids,
        ).create({'payment_date': fields.Date.today()})
        payment_register.action_create_payments()
        self.env.flush_all()

        report_paid = self.env['sale.commission.partner.report'].search([
            ('partner_id', '=', self.partner_agent.id),
            ('source_id', '=', f'account.move,{invoice.id}'),
        ])
        self.assertTrue(report_paid, "Paid invoice should appear in partner commission report")
        self.assertAlmostEqual(report_paid.achieved, 5.0, msg="Achieved should be margin (10 - 5)")
        self.assertAlmostEqual(report_paid.commission, 0.25, msg="Commission should be 5% of margin")
        invoice_line = invoice.invoice_line_ids.filtered(lambda line: line.agent_id)
        self.assertTrue(invoice_line.commission_locked)
        self.assertAlmostEqual(invoice_line.commission_amount, 0.25)

        margin_plan.achievement_ids.rate = 0.10
        self.env.flush_all()
        report_after_rate_change = self.env['sale.commission.partner.report'].search([
            ('partner_id', '=', self.partner_agent.id),
            ('source_id', '=', f'account.move,{invoice.id}'),
        ])
        self.assertAlmostEqual(report_after_rate_change.commission, 0.25, msg="Locked commission must ignore plan rate changes")

    def test_commission_locked_on_invoice_post(self):
        """Non margin_invoice_paid commissions are locked when the invoice is posted."""
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
        invoice = so._create_invoices()
        invoice.action_post()

        invoice_line = invoice.invoice_line_ids.filtered(lambda line: line.agent_id)
        self.assertTrue(invoice_line.commission_locked)
        self.assertAlmostEqual(invoice_line.commission_amount, 10.0)

        self.commission_plan.achievement_ids.rate = 0.20
        self.env.flush_all()
        report_line = self.env['sale.commission.partner.report'].search([
            ('partner_id', '=', self.partner_agent.id),
            ('source_id', '=', f'account.move,{invoice.id}'),
        ])
        self.assertAlmostEqual(report_line.commission, 10.0, msg="Locked commission must ignore plan rate changes")

        so.order_line.invalidate_recordset(['commission_amount'])
        self.assertAlmostEqual(so.order_line.commission_amount, 10.0, msg="Locked SO commission must ignore plan rate changes")

    def test_sales_user_can_compute_partner_commission(self):
        """Sales users must read commission plan rules without Sales Administrator rights."""
        sales_user = self.env['res.users'].create({
            'login': 'sales_commission_user',
            'partner_id': self.env['res.partner'].create({
                'name': 'Sales Commission User',
                'email': 'sales_commission_user@example.com',
            }).id,
            'group_ids': [Command.set(self.env.ref('sales_team.group_sale_salesman').ids)],
        })
        so = self.env['sale.order'].with_user(sales_user).create({
            'partner_id': self.partner_customer.id,
            'agent_id': self.partner_agent.id,
            'order_line': [Command.create({
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'price_unit': 100.0,
            })],
        })
        self.assertAlmostEqual(so.order_line.commission_amount, 10.0)
        so.with_user(sales_user).action_confirm()
        self.assertTrue(so.order_line.commission_locked)

    def test_draft_commission_plan_not_applied_on_sale_order(self):
        """Draft commission plans must not calculate partner commission on quotations."""
        draft_plan = self.env['sale.commission.plan'].create({
            'name': 'Draft only plan',
            'user_type': 'partner',
            'company_id': self.env.company.id,
            'achievement_ids': [Command.create({
                'type': 'margin_invoice_paid',
                'rate': 0.125,
            })],
        })
        agent = self.env['res.partner'].create({'name': 'Draft Agent'})
        agent.write({
            'commission_plan_ids': [Command.create({
                'plan_id': draft_plan.id,
                'date_from': fields.Date.today(),
            })]
        })
        product = self.env['product.product'].create({
            'name': 'Draft Product',
            'list_price': 10.0,
            'standard_price': 5.0,
            'type': 'service',
        })
        so = self.env['sale.order'].create({
            'partner_id': self.partner_customer.id,
            'agent_id': agent.id,
            'order_line': [Command.create({
                'product_id': product.id,
                'product_uom_qty': 1,
                'price_unit': 10.0,
            })],
        })
        self.assertAlmostEqual(so.order_line.commission_amount, 0.0)

        draft_plan.action_approve()
        so.order_line.invalidate_recordset(['commission_amount'])
        so.order_line._compute_commission_amount()
        self.assertAlmostEqual(so.order_line.commission_amount, 0.625)

    def test_commission_plan_applies_to_multiple_companies(self):
        """One commission plan can apply to several companies."""
        company_b = self.env['res.company'].create({'name': 'Commission Company B'})
        self.commission_plan.write({
            'company_ids': [Command.set([self.env.company.id, company_b.id])],
        })
        self.assertFalse(self.commission_plan.company_id)
        self.assertEqual(len(self.commission_plan.company_ids), 2)

        so_company_a = self.env['sale.order'].create({
            'partner_id': self.partner_customer.id,
            'agent_id': self.partner_agent.id,
            'order_line': [Command.create({
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'price_unit': 100.0,
            })],
        })
        so_company_b = self.env['sale.order'].with_company(company_b).create({
            'partner_id': self.partner_customer.id,
            'agent_id': self.partner_agent.id,
            'order_line': [Command.create({
                'product_id': self.product.id,
                'product_uom_qty': 2,
                'price_unit': 100.0,
            })],
        })
        self.assertAlmostEqual(so_company_a.order_line.commission_amount, 10.0)
        self.assertAlmostEqual(so_company_b.order_line.commission_amount, 20.0)

        company_c = self.env['res.company'].create({'name': 'Commission Company C'})
        so_company_c = self.env['sale.order'].with_company(company_c).create({
            'partner_id': self.partner_customer.id,
            'agent_id': self.partner_agent.id,
            'order_line': [Command.create({
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'price_unit': 100.0,
            })],
        })
        self.assertAlmostEqual(so_company_c.order_line.commission_amount, 0.0)

    def test_commission_rule_matches_parent_category(self):
        """Plan rules on a parent category apply to products in child categories."""
        parent_category = self.env['product.category'].create({'name': 'Microsoft CSP'})
        child_category = self.env['product.category'].create({
            'name': 'Microsoft 365',
            'parent_id': parent_category.id,
        })
        product = self.env['product.product'].create({
            'name': 'M365 Product',
            'categ_id': child_category.id,
            'list_price': 100.0,
            'type': 'service',
        })
        parent_plan = self.env['sale.commission.plan'].create({
            'name': 'Parent Category Plan',
            'user_type': 'partner',
            'company_id': self.env.company.id,
            'achievement_ids': [Command.create({
                'type': 'amount_sold',
                'product_categ_id': parent_category.id,
                'rate': 0.15,
            })],
        })
        parent_plan.action_approve()
        self.partner_agent.write({
            'commission_plan_ids': [Command.create({
                'plan_id': parent_plan.id,
                'date_from': fields.Date.today(),
            })]
        })
        so = self.env['sale.order'].create({
            'partner_id': self.partner_customer.id,
            'agent_id': self.partner_agent.id,
            'order_line': [Command.create({
                'product_id': product.id,
                'product_uom_qty': 1,
                'price_unit': 100.0,
            })],
        })
        self.assertAlmostEqual(so.order_line.commission_amount, 15.0)

    def test_bulk_refresh_partner_commissions(self):
        """Existing sale order lines can be recomputed in bulk after plan changes."""
        so = self.env['sale.order'].create({
            'partner_id': self.partner_customer.id,
            'agent_id': self.partner_agent.id,
            'order_line': [Command.create({
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'price_unit': 100.0,
            })],
        })
        so.order_line.write({'commission_amount': 0.0})
        self.commission_plan.achievement_ids.rate = 0.20
        wizard = self.env['sale.commission.refresh.wizard'].create({
            'plan_id': self.commission_plan.id,
            'order_state': 'all',
            'include_locked': False,
        })
        wizard.action_refresh()
        so.order_line.invalidate_recordset(['commission_amount'])
        self.assertAlmostEqual(so.order_line.commission_amount, 20.0)

