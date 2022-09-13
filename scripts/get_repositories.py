import json
from sys import argv
from typing import List

import boto3
from mypy_boto3_cloudformation import CloudFormationClient
from mypy_boto3_dynamodb.service_resource import DynamoDBServiceResource, Table


def main():
    stack_name = get_stack_name()
    table_name = get_table_name(stack_name)
    repositories = get_repositories(table_name)
    json.dump(repositories, open("repositories.json", "w"), indent=2)


def get_stack_name() -> str:
    return argv[1]


def get_table_name(stack_name: str) -> str:
    client: CloudFormationClient = boto3.client("cloudformation")
    resp = client.describe_stacks(StackName=stack_name)
    outputs = {x["OutputKey"]: x["OutputValue"] for x in resp["Stacks"][0]["Outputs"]}
    return outputs["TableName"]


def get_repositories(name_table: str) -> List[str]:
    resource: DynamoDBServiceResource = boto3.resource("dynamodb")
    table = resource.Table(name_table)

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


if __name__ == "__main__":
    main()
