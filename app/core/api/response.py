def success(data=None, message="success", meta=None):
    return {
        "success": True,
        "message": message,
        "data": data,
        "meta": meta or {},
    }


def error(message="error", error_code="GENERIC_ERROR", data=None):
    return {
        "success": False,
        "message": message,
        "error_code": error_code,
        "data": data,
    }