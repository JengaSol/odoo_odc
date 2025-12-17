"""
Test script for Bongapoints billing format parsing.
This script verifies that the new parsing logic correctly extracts data from Bongapoints format.
"""

# Sample text extracted from Bongapoints PDF (simplified for testing)
test_text = """
TAX INVOICE SUMMARY
Name Reference NO. INVOICE NO. Net Amount VAT EXCISE BILLED AMOUNT
ODC SBT AFRICA LIMI
TED 1-460477391864 B1-40022628051 9,616.81 1,769.51 1,442.55 12,828.87
9,616.81 1,769.51 1,442.55 12,828.87

Charge Share USG Parent Account (01/11/2025 - 30/11/2025) Telephony Charge Share -709915000 166.97
Charge Share USG Parent Account (01/11/2025 - 30/11/2025) Telephony Charge Share -709915103 112.42
Charge Share USG Parent Account (01/11/2025 - 30/11/2025) Telephony Charge Share -709915106 1,308.80
Charge Share USG Parent Account (01/11/2025 - 30/11/2025) Telephony Charge Share -709915108 92.41
Charge Share USG Parent Account (01/11/2025 - 30/11/2025) Telephony Charge Share -709915114 116.12

24/10/2025 B/F-P1-1000100231102807 TJO5E88TVF PYT:-17,523.00
21/11/2025 P1-100010024834307515 TKL5EAS5MM PYT:-15,328.00
"""

import re

def test_tax_invoice_summary():
    """Test TAX INVOICE SUMMARY pattern."""
    pattern = re.compile(
        r"TAX INVOICE SUMMARY.*?"
        r"Name\s+Reference\s+NO\.\s+INVOICE\s+NO\..*?"
        r"([\s\S]+?)"
        r"(\d+-\d+)\s+"
        r"(B\d+-\d+)\s+"
        r"([\d,.-]+)\s+"
        r"([\d,.-]+)\s+"
        r"([\d,.-]+)\s+"
        r"([\d,.-]+)",
        re.MULTILINE
    )
    
    match = pattern.search(test_text)
    if match:
        print("✓ TAX INVOICE SUMMARY pattern matched!")
        print(f"  Reference NO: {match.group(2)}")
        print(f"  Invoice NO: {match.group(3)}")
        print(f"  Net Amount: {match.group(4)}")
        print(f"  VAT: {match.group(5)}")
        print(f"  Excise: {match.group(6)}")
        print(f"  Total: {match.group(7)}")
    else:
        print("✗ TAX INVOICE SUMMARY pattern did not match")

def test_charge_share():
    """Test Charge Share pattern."""
    pattern = re.compile(
        r"Charge Share USG Parent Account.*?"
        r"-(?P<subscriber>\d+)\s+"
        r"(?P<amount>[\d,.-]+)",
        re.MULTILINE
    )
    
    matches = list(pattern.finditer(test_text))
    print(f"\n✓ Found {len(matches)} Charge Share entries:")
    for match in matches:
        data = match.groupdict()
        print(f"  Subscriber: {data['subscriber']}, Amount: {data['amount']}")

def test_payments():
    """Test payment pattern."""
    pattern = re.compile(
        r"(?P<date>\d{2}/\d{2}/\d{4})\s+(?P<ref1>\S+)\s+(?P<ref2>\S+)\s+(?P<type>PYT|ADJ|INV|TRF):(?P<amount>[\d,.-]+)",
        re.MULTILINE
    )
    
    matches = list(pattern.finditer(test_text))
    print(f"\n✓ Found {len(matches)} Payment entries:")
    for match in matches:
        data = match.groupdict()
        print(f"  Date: {data['date']}, Type: {data['type']}, Amount: {data['amount']}")

def test_format_detection():
    """Test format auto-detection."""
    is_bongapoints = 'Charge Share USG Parent Account' in test_text
    print(f"\n✓ Format detection: {'Bongapoints' if is_bongapoints else 'Standard'}")

if __name__ == "__main__":
    print("=" * 60)
    print("Bongapoints Billing Format - Parser Test")
    print("=" * 60)
    
    test_format_detection()
    test_tax_invoice_summary()
    test_charge_share()
    test_payments()
    
    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)
