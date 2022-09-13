# github-pr-notification
## 概要
- GitHubのPRの状態を定期的に取得してSlackに投げるためのアプリケーション
    - 実行周期は30分
    - 監視対象のリポジトリはDynamoDBで管理
    - GitHubのPersonal access tokensを使って以下の条件どちらかを満たすPRを通知する
        - 自身が作成したPR
        - 自身がレビュアーになっているPR

## デプロイ方法
### 1. 環境構築
下記内容に加えてAWS CLIのインストールも行ってください。

```
$ pip install aws-sam-cli poetry
$ poetry install
```

### 2. アプリケーションをAWSにデプロイする
注意) Linux上で実行してください。Mac上でやると動かない可能性があります。

```bash
$ export ARTIFACT_BUCKET=“<LambdaのDeployに使用するS3 Bucket>”
$ make build package deploy
```

### 3. GitHubのTokenとSlackのIncoming WebhookのURLをSSM Parameterに保存する
```bash
$ make set-parameters
```

実行して、TokenやUrlを入力する。
GitHubのPersonal access tokenはrepoの権限さえあれば十分です。
(必要な権限の絞り込みはできてません)
![9005536208251169  スクリーンショット 2022-09-13 14 21 05](https://user-images.githubusercontent.com/13509891/189815629-fb0afa28-0461-4cd4-91c7-3419c3d6e67e.png)

### 4. 対象とするリポジトリを登録する
```bash
$ cp repositories.sample.json repositories.json
$ vi repositories.json # 中身を書き換えて、対象のリポジトリを書き込む
$ make put-monitoring-repositories
```