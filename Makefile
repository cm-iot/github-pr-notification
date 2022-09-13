SHELL = /usr/bin/env bash -xeuo pipefail

STACK_NAME:=github-pr-notification

ipython:
	PYTHONPATH=src \
	poetry run ipython

isort:
	poetry run isort src scripts

black:
	poetry run black src scripts

format: isort black

build:
	rm -rf layer
	mkdir layer
	poetry export -f requirements.txt -o layer/requirements.txt --without-hashes
	pip install -r layer/requirements.txt -t layer/python/

sam-validate:
	sam validate -t sam.yml

package:
	uuidgen > src/uuid.txt
	sam package \
		--s3-bucket ${ARTIFACT_BUCKET} \
		--s3-prefix ${STACK_NAME} \
		--template-file sam.yml \
		--output-template-file template.yml

deploy:
	sam deploy \
		--stack-name ${STACK_NAME} \
		--template-file template.yml \
		--capabilities CAPABILITY_IAM \
		--no-fail-on-empty-changeset

describe:
	aws cloudformation describe-stacks \
		--stack-name ${STACK_NAME} \
		--query Stacks[0].Outputs

set-parameters:
	poetry run python scripts/create_ssm_parameters.py

get-monitoring-repositories:
	poetry run python scripts/get_repositories.py ${STACK_NAME}

put-monitoring-repositories:
	poetry run python scripts/put_repositories.py ${STACK_NAME}
