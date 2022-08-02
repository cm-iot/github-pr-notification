import json
import logging.config
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from functools import wraps
from logging import Logger, getLogger
from typing import Any, Callable, List
from uuid import uuid4

import boto3
import botocore

from .borg_data import BorgData
from .borg_default import BorgDefaultFunctions, CustomDefaultFunction

ENVIRONMENT_VARIABLES_NOT_LOGGING = [
    "AWS_ACCESS_KEY_ID",
    "AWS_DEFAULT_REGION",
    "AWS_LAMBDA_LOG_GROUP_NAME",
    "AWS_LAMBDA_LOG_STREAM_NAME",
    "AWS_REGION",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SECURITY_TOKEN",
    "AWS_SESSION_TOKEN",
    "_AWS_XRAY_DAEMON_ADDRESS",
    "_AWS_XRAY_DAEMON_PORT",
    "AWS_XRAY_DAEMON_ADDRESS",
]


@dataclass(frozen=True)
class DummyContext:
    aws_request_id: str


class MyLogger(object):
    logger: Logger
    borg_data = BorgData()
    borg_default_function = BorgDefaultFunctions()
    stack_function_memo: List[dict] = []

    def __init__(self, name: str):
        file_path = os.path.join(
            os.path.dirname(os.path.realpath(__file__)), "logging.json"
        )
        logging.config.dictConfig(json.load(open(file_path)))
        self.logger = getLogger(name)

    def set_shared_data(self, key: str, value: Any):
        self.borg_data.data[key] = value

    def has_shared_data(self, key) -> bool:
        return key in self.borg_data.data

    def remove_shared_data(self, key):
        if key in self.borg_data.data:
            del self.borg_data.data[key]

    def add_default_function(self, func: CustomDefaultFunction):
        self.borg_default_function.functions.append(func)

    def add_functional_data(self, key: str, value: Any):
        if len(self.stack_function_memo) > 0:
            return
        node = self.stack_function_memo[-1]
        if not isinstance(node, dict):
            return
        node[key] = value
        self.stack_function_memo[-1] = node

    def info(self, msg: str, *args, **kwargs):
        self.logger.info(msg, *args, exc_info=True, extra={"additional_data": kwargs})

    def debug(self, msg: str, *args, **kwargs):
        self.logger.debug(msg, *args, exc_info=True, extra={"additional_data": kwargs})

    def warning(self, msg: str, *args, **kwargs):
        self.logger.warning(
            msg, *args, exc_info=True, extra={"additional_data": kwargs}
        )

    def error(self, msg: str, *args, **kwargs):
        self.logger.error(msg, *args, exc_info=True, extra={"additional_data": kwargs})

    def fatal(self, msg: str, *args, **kwargs):
        self.logger.fatal(msg, *args, exc_info=True, extra={"additional_data": kwargs})

    def logging_handler(self, with_return: bool = True) -> Callable:
        def wrapper(handler: Callable) -> Callable:
            @wraps(handler)
            def process(event: dict, context: DummyContext):
                try:
                    self.set_shared_data("aws_request_id", context.aws_request_id)
                except Exception as e:
                    self.warning(f"error occurred in set aws request id: {e}")

                try:
                    self.debug(
                        "event, python/boto3/botocore version, environment variables",
                        event=event,
                        versions={
                            "python": sys.version,
                            "boto3": boto3.__version__,
                            "botocore": botocore.__version__,
                        },
                        environments={
                            k: v
                            for k, v in os.environ.items()
                            if k not in ENVIRONMENT_VARIABLES_NOT_LOGGING
                        },
                    )
                except Exception as e:
                    self.warning(
                        f"error occurred in logging event and version, environment variables: {e}"
                    )

                try:
                    result = handler(event, context)
                    if with_return:
                        self.debug("handler result", result=result)
                    return result
                except Exception as e:
                    self.error(f"error occurred in handler: {e}")
                    raise

            return process

        return wrapper

    def logging_function(
        self, with_arg: bool = True, with_return: bool = True, write_log: bool = False
    ) -> Callable:
        def wrapper(func) -> Callable:
            @wraps(func)
            def process(*args, **kwargs):
                func_id = str(uuid4())
                name = func.__name__
                self.stack_function_memo.append({})

                log_start_options = {"func_id": func_id, "function_name": name}
                if with_arg:
                    log_start_options["args"] = args
                    log_start_options["kwargs"] = kwargs
                if write_log:
                    self.debug(
                        f"function {name} start ({func_id})", **log_start_options
                    )

                result = None
                is_succeed = True
                dt_start = datetime.now()
                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception:
                    is_succeed = False
                    raise
                finally:
                    dt_end = datetime.now()
                    delta_duration = dt_end - dt_start
                    memo = self.stack_function_memo[-1]
                    del self.stack_function_memo[-1]
                    status = "success" if is_succeed else "failed"
                    log_end_options = {
                        "func_id": func_id,
                        "function_name": name,
                        "is_succeed": is_succeed,
                        "duration": delta_duration.total_seconds(),
                        "memo": memo,
                    }

                    if with_return and is_succeed:
                        log_end_options["result"] = result
                    if write_log or not is_succeed:
                        msg = f"function {name} end ({status}) ({func_id}) (Duration: {delta_duration})"
                        if not is_succeed:
                            log_end_options["args"] = args
                            log_end_options["kwargs"] = kwargs
                        self.debug(msg, **log_end_options)

            return process

        return wrapper
