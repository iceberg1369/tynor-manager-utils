
try:
    import ghasedak_sms
    print("ghasedak_sms imported successfully")
    import config
    print(f"API KEY: {config.GHASEDAK_OTP_API_KEY}")
    sms = ghasedak_sms.Ghasedak(apikey=config.GHASEDAK_OTP_API_KEY)
    print("Ghasedak initialized:", sms)
except Exception as e:
    print(f"Error: {e}")
