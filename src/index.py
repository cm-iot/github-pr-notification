import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from urllib.request import Request, urlopen

import boto3
from github import Github
from github.PullRequest import PullRequest
from github.Repository import Repository
from mypy_boto3_dynamodb import DynamoDBServiceResource
from mypy_boto3_dynamodb.service_resource import Table
from mypy_boto3_ssm import SSMClient

from logger import MyLogger

jst = timezone(offset=timedelta(hours=+9), name="JST")


@dataclass(frozen=True)
class EnvironmentVariables:
    dynamodb_table: str


@dataclass(frozen=True)
class Parameters:
    github_token: str
    webhook_url: str


@dataclass(frozen=True)
class OutputRepositoryInfo:
    full_name: str


@dataclass(frozen=True)
class OutputPullRequestInfo:
    is_opener: bool
    number: int
    url: str
    title: str
    created_at: str


@dataclass(frozen=True)
class Target:
    repository: OutputRepositoryInfo
    pull_requests: List[OutputPullRequestInfo]


logger = MyLogger(__name__)


@logger.logging_handler()
def handler(event, context):
    main()


@logger.logging_function()
def main(
    ssm_client: SSMClient = boto3.client("ssm"),
    dynamodb_client: DynamoDBServiceResource = boto3.resource("dynamodb"),
):
    env = load_environ()
    params = get_parameters(ssm_client)
    repositories = get_repository_names(env.dynamodb_table, dynamodb_client)

    targets = get_targets(repositories, params.github_token)

    if len(targets) == 0:
        return

    body = create_body_v2(targets)
    post_to_slack(body, params.webhook_url)


@logger.logging_function()
def load_environ() -> EnvironmentVariables:
    return EnvironmentVariables(
        **{k: os.environ[v] for k, v in {"dynamodb_table": "DYNAMODB_TABLE"}.items()}
    )


@logger.logging_function()
def get_parameters(ssm_client: SSMClient) -> Parameters:
    option = {"Path": "/GithubPrNotification/", "WithDecryption": True}
    logger.add_functional_data("option", option)
    resp = ssm_client.get_parameters_by_path(**option)
    logger.add_functional_data("response", resp)

    params = {x["Name"]: x["Value"] for x in resp["Parameters"]}
    return Parameters(
        github_token=params["/GithubPrNotification/GithubToken"],
        webhook_url=params["/GithubPrNotification/WebhookUrl"],
    )


@logger.logging_function()
def get_repository_names(
    table_name: str, dynamodb_resource: DynamoDBServiceResource
) -> List[str]:
    table: Table = dynamodb_resource.Table(table_name)

    result = []
    is_first = True
    token = None
    while token is not None or is_first:
        if is_first:
            is_first = False
        option = {}
        if token is not None:
            option["ExclusiveStartKey"] = token
        resp = table.scan(**option)
        result += [x["repository"] for x in resp.get("Items", [])]
        token = resp.get("LastEvaluatedKey")

    return result


@logger.logging_function()
def post_to_slack(body: dict, webhook_url: str):
    req = Request(
        webhook_url,
        method="POST",
        headers={"Content-Type": "application/json"},
        data=json.dumps(body).encode("utf-8"),
    )
    urlopen(req)


@logger.logging_function()
def is_pull_request_target(pull_request: PullRequest, user_id: str) -> bool:
    if pull_request.draft:
        return False
    if pull_request.user.login == user_id:
        return True
    for x in pull_request.get_review_requests():
        for reviewer in x:
            if reviewer.login == user_id:
                return True
    return False


@logger.logging_function()
def get_output_pull_request_info(
    pr: PullRequest, user_id: str
) -> OutputPullRequestInfo:
    return OutputPullRequestInfo(
        is_opener=pr.user.login == user_id,
        number=pr.number,
        url=pr.html_url,
        title=pr.title,
        created_at=str(pr.created_at),
    )


@logger.logging_function()
def get_targets(names_repository: List[str], github_token: str) -> List[Target]:
    g = Github(github_token)
    user_id = g.get_user().login
    result = []
    for name_repository in names_repository:
        try:
            repository = g.get_repo(name_repository)
            pulls = [
                get_output_pull_request_info(x)
                for x in repository.get_pulls(state="open")
                if is_pull_request_target(x, user_id)
            ]
            if len(pulls) > 0:
                result.append(
                    Target(
                        repository=OutputRepositoryInfo(full_name=repository.full_name),
                        pull_requests=pulls,
                    )
                )
        except Exception as e:
            logger.warning(f"error occurred: {e}")
    return result


@logger.logging_function()
def create_body_v2(targets: List[Target]) -> dict:
    blocks = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"<!here> ({datetime.now(jst)})"},
        }
    ]
    for target in targets:
        blocks += [
            {"type": "divider"},
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": target.repository.full_name,
                    "emoji": False,
                },
            },
        ]
        blocks += [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "`{0}` <{1}|#{2} {3}> ({4} UTC)".format(
                        "opener" if pr.is_opener else "reviewer",
                        pr.url,
                        pr.number,
                        pr.title,
                        pr.created_at,
                    ),
                },
            }
            for pr in target.pull_requests
        ]
    return {"blocks": blocks}
