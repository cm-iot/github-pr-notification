import json
from datetime import datetime, timezone
from logging import Formatter, LogRecord
from typing import List, Optional

from .borg_data import BorgData
from .borg_default import BorgDefaultFunctions

borg_default = BorgDefaultFunctions()
borg_data = BorgData()


class JsonLogFormatter(Formatter):
    def convert_exc_info(self, record: LogRecord) -> Optional[List[str]]:
        if record.exc_info is None:
            return None
        value = self.formatException(record.exc_info)
        return value.split("\n")

    def format(self, record: LogRecord) -> str:
        result = {
            "name": record.name,
            "level": record.levelname,
            "msg": record.getMessage(),
            "unixtime": record.created,
            "datetime": str(datetime.fromtimestamp(record.created, timezone.utc)),
            "exc_info": self.convert_exc_info(record),
            "pathname": record.pathname,
            "shared_data": {k: v for k, v in borg_data.data.items()},
            "additional_data": {
                k: v for k, v in record.__dict__.get("additional_data", {}).items()
            },
        }
        return json.dumps(result, ensure_ascii=False, default=borg_default.default)
