def get_byte_length(text):
    """
    한글을 포함한 문자열의 바이트 수를 계산합니다. (EUC-KR 기반 90바이트 기준)
    일부 시스템에서는 80바이트, 알리고 등은 90바이트를 기준으로 할 수 있습니다.
    """
    return len(text.encode('euc-kr'))

def determine_msg_type(text, manual_type=None):
    """
    텍스트 길이에 따라 SMS 또는 LMS를 판별합니다.
    manual_type이 지정된 경우 해당 타입을 우선합니다.
    """
    if manual_type in ["SMS", "LMS", "MMS"]:
        return manual_type
        
    byte_len = get_byte_length(text)
    if byte_len <= 90:
        return "SMS"
    else:
        return "LMS"

if __name__ == "__main__":
    test1 = "안녕하세요"
    test2 = "이것은 90바이트를 넘기기 위한 매우 긴 테스트 메시지입니다. " * 5
    print(f"Test 1: {get_byte_length(test1)} bytes -> {determine_msg_type(test1)}")
    print(f"Test 2: {get_byte_length(test2)} bytes -> {determine_msg_type(test2)}")
