"""Serialize Tea/Dara SDK models to JSON-friendly dicts."""


def tea_to_plain(obj):
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if hasattr(obj, "to_map"):
        m = obj.to_map()
        if not isinstance(m, dict):
            return m
        return {k: tea_to_plain(v) for k, v in m.items()}
    if isinstance(obj, dict):
        return {k: tea_to_plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [tea_to_plain(x) for x in obj]
    return str(obj)


def openapi_response_to_dict(resp) -> dict:
    if resp is None:
        return {}
    out: dict = {}
    if getattr(resp, "headers", None) is not None:
        h = resp.headers
        out["headers"] = dict(h) if not isinstance(h, dict) else h
    if getattr(resp, "status_code", None) is not None:
        out["status_code"] = resp.status_code
    if getattr(resp, "body", None) is not None:
        out["body"] = tea_to_plain(resp.body)
    return out
