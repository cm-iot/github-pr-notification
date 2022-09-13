import json
from sys import argv
from typing import List

import boto3
from mypy_boto3_cloudformation import CloudFormationClient
from mypy_boto3_dynamodb.service_resource import DynamoDBServiceResource, Table
from prompt_toolkit import prompt


def main():
    name_json = input_json_name()
    repositories_latest = load_json(name_json)
    stack_name = get_stack_name()
    table_name = get_table_name(stack_name)
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)
    repositories_old = get_repositories(table)
    update_repositories(repositories_old, repositories_latest, table)
    print("put finish")


def input_json_name() -> str:
    return prompt("repository name array json file: ", default="repositories.json")


def load_json(path: str) -> List[str]:
    return json.load(open(path))


def get_stack_name() -> str:
    return argv[1]


def get_table_name(stack_name: str) -> str:
    client: CloudFormationClient = boto3.client("cloudformation")
    resp = client.describe_stacks(StackName=stack_name)
    outputs = {x["OutputKey"]: x["OutputValue"] for x in resp["Stacks"][0]["Outputs"]}
    return outputs["TableName"]


def get_repositories(table: Table) -> List[str]:
    token = None
    is_first = True
    result = []
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


def update_repositories(old: List[str], new: List[str], table: Table):
    union_old = set(old)
    union_new = set(new)

    targets_delete = union_old - union_new
    targets_insert = union_new - union_old

    with table.batch_writer() as batch:
        for name in targets_delete:
            batch.delete_item(Key={"repository": name})
        for name in targets_insert:
            batch.put_item(Item={"repository": name})


if __name__ == "__main__":
    main()
