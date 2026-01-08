from ussd import parse_ussd_message, extract_ussd_credit

print("Running USSD Parser Tests...\n")

# Test 1: Plain Text English Response
raw_1 = 'CUSD: 0, "Etebar:150,918Rial\nShegeftangiz:0Rial", 1'
print(f"Test 1 Input: {raw_1}")
decoded_1 = parse_ussd_message(raw_1)
print(f"Decoded 1: {decoded_1}")
credit_1 = extract_ussd_credit(decoded_1)
print(f"Credit 1: {credit_1}")
assert credit_1 == "150918"

# Test 2: Hex Encoded (Legacy)
# "1000ریال" in UTF-16BE hex: 0031003000300030063106cc06270644
hex_content = "0031003000300030063106cc06270644"
raw_2 = f'+CUSD: 0, "{hex_content}", 15'
print(f"\nTest 2 Input: {raw_2}")
decoded_2 = parse_ussd_message(raw_2)
print(f"Decoded 2: {decoded_2}")
credit_2 = extract_ussd_credit(decoded_2)
print(f"Credit 2: {credit_2}")
assert credit_2 == "1000"

print("\n✅ All Tests Passed!")
