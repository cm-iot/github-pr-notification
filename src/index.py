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


logger = MyLogger("__name__")


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
    targets, target_id = get_notification_target(repositories, params.github_token)
    body = create_body(targets, target_id)
    if body is None:
        return
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
def is_reviewer(pull: PullRequest, target_id: str) -> bool:
    for x in pull.get_review_requests():
        for user in x:
            if user.login == target_id:
                return True
    return False


@logger.logging_function()
def is_opener(pull: PullRequest, target_id: str) -> bool:
    return pull.user.login == target_id


@logger.logging_function()
def get_notification_target(
    repositories: List[str], github_token: str
) -> Tuple[Dict[Repository, List[PullRequest]], str]:
    g = Github(github_token)
    target_id = g.get_user().login
    result = {}
    for name in repositories:
        repo = g.get_repo(name)
        pulls = [
            x
            for x in repo.get_pulls(state="open")
            if is_reviewer(x, target_id) or is_opener(x, target_id)
        ]
        if len(pulls) == 0:
            continue
        result[repo] = pulls

    return result, target_id


@logger.logging_function()
def create_text(pr: PullRequest, target_id: str) -> str:
    pr_type = "opener" if is_opener(pr, target_id) else "reviewer"
    return f"`{pr_type}` <{pr.html_url}|#{pr.number} {pr.title}> ({pr.created_at} UTC)"


@logger.logging_function()
def create_body(
    targets: Dict[Repository, List[PullRequest]], target_id: str
) -> Optional[dict]:
    if len(targets) == 0:
        return None
    blocks = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"<!here> ({datetime.now(jst)})"},
        }
    ]
    for repo, pulls in targets.items():
        if len(pulls) == 0:
            continue
        blocks += [
            {"type": "divider"},
            {
                "type": "header",
                "text": {"type": "plain_text", "text": repo.full_name, "emoji": False},
            },
        ]
        blocks += [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": create_text(pr, target_id),
                },
            }
            for pr in pulls
        ]

    return {"blocks": blocks}


@logger.logging_function()
def post_to_slack(body: dict, webhook_url: str):
    req = Request(
        webhook_url,
        method="POST",
        headers={"Content-Type": "application/json"},
        data=json.dumps(body).encode("utf-8"),
    )
    urlopen(req)
