SHELL = /usr/bin/env bash -xeuo pipefail

stack_name:=github-pr-notification

ipython:
	PYTHONPATH=src \
	poetry run ipython

isort:
	poetry run isort src

black:
	poetry run black src

format: isort black

build:
	rm -rf layer
	mkdir layer
	poetry export -f requirements.txt -o layer/requirements.txt --without-hashes
	pip install -r layer/requirements.txt -t layer/python/

sam-validate:
	sam validate -t sam.yml

package:
	sam package \
		--s3-bucket ${ARTIFACT_BUCKET} \
		--s3-prefix library-base \
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
