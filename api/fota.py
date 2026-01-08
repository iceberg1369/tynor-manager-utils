# fota.py
from fastapi import APIRouter, Query, Response
from fastapi.responses import JSONResponse
from datetime import datetime
import database

router = APIRouter()

def is_imei(imei: str) -> bool:
    """
    Validate IMEI using Luhn algorithm.
    """
    if not imei or len(imei) != 15 or not imei.isdigit():
        return False
    
    digits = [int(d) for d in imei]
    check_digit = digits.pop()
    
    # Luhn algorithm:
    # 1. Double every second digit from the right
    # 2. Sum digits of the products
    # 3. Sum all results + unaffected digits
    
    # Note: PHP code implementation:
    # loop through digits (0 to 13)
    # logic seems slightly different from standard Luhn but we port it exactly as is?
    # Actually, PHP code: 
    # foreach($digits as $key => $n)
    #   if($key & 1) -> double...
    # Wait, PHP arrays are 0-indexed.
    # $digits has 14 elements (0..13)
    # key 0 (1st digit) -> even (key&1 == 0) -> no double
    # key 1 (2nd digit) -> odd (key&1 == 1) -> double
    # This matches standard Luhn if we count from left 1-based index (evens doubled). 
    # usually Luhn doubles every second from right.
    # PHP: 14 digits. Key 13 (last) is odd -> double.
    
    log = []
    for i, n in enumerate(digits):
        val = n
        if i & 1:  # if index is odd (1, 3, 5...)
            double_val = n * 2
            # Sum double digits (e.g. 18 -> 1+8=9)
            val = sum(int(d) for d in str(double_val))
        log.append(val)
        
    total_sum = sum(log) * 9
    
    # PHP: return substr($sum, -1) == $imei_last;
    calculated_check = str(total_sum)[-1]
    
    return calculated_check == str(check_digit)


@router.get("/fota.php")
@router.post("/fota.php")
async def handle_fota(
    imei: str = Query(None),
    sr: str = Query(None),
    d: str = Query(None),
    fw: str = Query(None),
    rev: str = Query(None)
):
    # 1. Validation
    if not imei:
        return JSONResponse(status_code=400, content={'result': 'Error', 'message': "no imei"})
    
    if not is_imei(imei):
        # The PHP code returns 400 for invalid IMEI
        return JSONResponse(status_code=400, content={'result': 'Error', 'message': "invalid imei"})

    if not sr:
        return JSONResponse(status_code=400, content={'result': 'Error', 'message': "no serial"})
    
    if not d:
        return JSONResponse(status_code=400, content={'result': 'Error', 'message': "no device"})
    
    if not fw:
        return JSONResponse(status_code=400, content={'result': 'Error', 'message': "no firmware version"})
    
    if not rev:
        return JSONResponse(status_code=400, content={'result': 'Error', 'message': "no revision"})

    # Hardcoded check from PHP
    if imei == "867717033890519":
        return JSONResponse(content={
            'result': 'SUCCESS', 
            'download': 'ftp://avl:123456@upgrade2.hiro-tracker.com/90/67329/1', 
            'firmware': "1.7.0", 
            'date': "dfdfd"
        })

    # Database logic
    try:
        device_id = int(d)
        fw_ver = int(fw)
        rev_ver = int(rev)
        
        rows = database.find_newer_firmware(device=device_id, rev=rev_ver, current_fw=fw_ver)
        
        dbres = 0
        response_data = None
        
        if rows:
            # take the first one (PHP logic loops but outputs 1st and arguably stops due to echo)
            row = rows[0]
            response_data = {
                'result': 'SUCCESS', 
                'download': row["download_path"], 
                'firmware': row["firmware"], 
                'date': row["date"]
            }
            dbres = 1
        else:
            # Firmware not available
            response_data = {'result': 'Error', 'message': "firmware not avaiable"} # typo in PHP preserved? "avaiable"
            dbres = 2
            # PHP sets response code 400 here
    
    except Exception as e:
        print(f"❌ FOTA Logic Error: {e}")
        return JSONResponse(status_code=500, content={'result': 'ERROR', 'message': "internal error"})

    # Logging
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    database.log_fota_request(imei, sr, fw, d, rev, dbres, current_time)

    status_code = 200
    if dbres == 2:
        status_code = 400

    return JSONResponse(status_code=status_code, content=response_data)
