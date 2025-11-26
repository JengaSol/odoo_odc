# Sales Commission - Margin on Paid Invoices

## Overview

This module extends the Odoo Enterprise `sale_commission` module to add a new achievement type: **"Margin (Invoices Fully Paid)"**.

## Features

- **New Achievement Type**: Add "Margin (Invoices Fully Paid)" to commission plans
- **Accurate Margin Calculation**: Uses product's current cost (`standard_price`) for margin calculation
- **Payment State Filtering**: Only includes invoices with `payment_state = 'paid'`
- **Credit Note Handling**: Properly deducts margin from credit notes (reversals)
- **Currency Conversion**: Handles multi-currency invoices correctly
- **Product/Category Filters**: Respects existing product and category filters on commission plans
- **Source Display**: Shows invoice numbers (e.g., INV/2025/0001) and sale order numbers (e.g., S00029) in the achievement report

## Installation

1. Ensure `sale_commission` and `sale_commission_margin` modules are installed
2. Update the apps list in Odoo
3. Install the `sale_commission_margin_paid` module

## Usage

1. Navigate to **Sales > Configuration > Commission Plans**
2. Create or edit a commission plan
3. Add a new achievement with type **"Margin (Invoices Fully Paid)"**
4. Set the commission rate (e.g., 0.10 for 10%)
5. Optionally add product or category filters
6. Approve the plan

## Technical Details

### Margin Calculation

The margin is calculated as:

```
margin = price_subtotal - (cost × quantity)
```

Where:
- `cost` = `standard_price` from the product template (current product cost)
- Currency conversion is applied automatically
- Credit notes are handled by negating the margin value

**Note**: Invoice lines don't have a historical cost field, so the current product `standard_price` is used for margin calculation.

### Payment State Filter

Only invoices with `payment_state = 'paid'` are included. Invoices with `payment_state = 'in_payment'` are excluded to ensure only fully settled invoices are counted.

### Dependencies

- `sale_commission`: Base commission functionality
- `sale_commission_margin`: Provides margin field on sale order lines

## License

OEEL-1 (Odoo Enterprise Edition License)
