from base64 import b64encode
from dataclasses import asdict, is_dataclass
from decimal import Decimal
from typing import Any, Callable, List, Tuple, Union

Jsonable = Union[dict, list, str, int, float, bool, None]
CustomDefaultReturn = Tuple[bool, Jsonable]
CustomDefaultFunction = Callable[[Any], CustomDefaultReturn]


class BorgDefaultFunctions:
    _shared_state = {}
    functions: List[CustomDefaultFunction] = []

    def __init__(self):
        self.__dict__ = self._shared_state

    def default(self, obj: Any) -> Jsonable:
        if isinstance(obj, Decimal):
            num = int(obj)
            return num if num == obj else float(obj)
        if isinstance(obj, bytes):
            try:
                return obj.decode()
            except Exception:
                return b64encode(obj).decode()
        if is_dataclass(obj):
            return asdict(obj)
        for func in self.functions:
            flag, value = func(obj)
            if flag:
                return value
        return {"type": str(type(obj)), "value": str(obj)}
