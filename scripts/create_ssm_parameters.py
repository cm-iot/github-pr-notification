from dataclasses import dataclass
from typing import Literal

import boto3
from mypy_boto3_ssm import SSMClient
from prompt_toolkit import prompt


@dataclass(frozen=True)
class Parameters:
    github_token: str
    slack_webhook_url: str


def main():
    params = input_values()
    if not confirm():
        return
    ssm = boto3.client("ssm")
    put_parameter(
        name="/GithubPrNotification/GithubToken",
        value=params.github_token,
        is_secure=True,
        ssm=ssm,
    )
    put_parameter(
        name="/GithubPrNotification/WebhookUrl",
        value=params.slack_webhook_url,
        is_secure=False,
        ssm=ssm,
    )
    print("finish: set parameters ")


def input_values() -> Parameters:
    print("input parameters.\n")
    github_token = prompt("github token: ").strip()
    slack_webhook_url = prompt("slack webhook url: ").strip()
    return Parameters(github_token, slack_webhook_url)


def confirm() -> bool:
    value = prompt("\ncreate parameters? [y/N]: ")
    return value.lower() in {"y", "yes"}


def put_parameter(name: str, value: str, is_secure: bool, ssm: SSMClient):
    if is_secure:
        ssm.put_parameter(Name=name, Value=value, Type="SecureString", Overwrite=True)
    else:
        ssm.put_parameter(Name=name, Value=value, Type="String", Overwrite=True)


if __name__ == "__main__":
    main()
