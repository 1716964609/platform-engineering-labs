# Lab 16 — 検証結果（Kratix Platform Contract / Flux / Gateway API）

## 1. 検証サマリー

- 実施日：**2026-10-31（JST）**。
- 対象：`kind-kratix-lab`。
- 結論：**自作WebService Platform APIのDay 1 Provisioning・L7 Hostname Routing・Day 2 Replica構成変更が成功**。
- 最終Platform Promise：`webservice v0.3.0`。
- 最終アプリケーション構成：`hello-web` Deployment **2/2 Ready**、Service、HTTPRoute `hello.lab.test`。
- GitへのPush：端末ログ上で確認。コミット `67f8125`（初版）、`14a0f3f`（Gateway API統合）。GitHub連携を通じたPrivate Repo内容の直接照合は未実施。

## 2. 実行結果一覧

| ID | 項目 | 実際の観測 | 判定 |
|---|---|---|---|
| R01 | Kratix Quick Start | `Kratix installation complete!`、Controller / Flux / SeaweedFS Running | PASS |
| R02 | 既存PostgreSQL Promise | `postgresql` Available、`example` Reconciled、PostgreSQL 16 | PASS |
| R03 | PostgreSQL Runtime | Pod `1/1 Running`、StatefulSet `1/1`、`pg_isready` が `accepting connections` | PASS |
| R04 | PostgreSQL SQL | `SELECT current_user, current_database(), 1` → `postgres\|postgres\|1` | PASS |
| R05 | WebService Promise v0.1.0 | Promise登録、CRD公開、`Available` | PASS |
| R06 | Schema Validation | `replicas: 99` → `should be less than or equal to 5` で拒否 | PASS |
| R07 | API Defaulting | `replicas` 省略で `spec.replicas: 2` に補完 | PASS |
| R08 | Pipeline v0.2.0 | `Generated Deployment and Service: default/hello-web`、Configure Job Complete | PASS |
| R09 | Kratix / GitOps Chain | Work、WorkPlacement `Ready`、Flux Bucket/Kustomization `Ready` | PASS |
| R10 | Deployment / Service | Nginx Deployment `2/2 Ready`、ClusterIP Service作成 | PASS |
| R11 | Service疎通 | `port-forward svc/hello-web 8082:80` → HTTP 200（nginx/1.27.5） | PASS |
| R12 | Gateway API導入 | GatewayClass `Accepted=True`、Gateway `Programmed=True` | PASS |
| R13 | Promise v0.3.0 | HTTPRoute生成、Gateway `Attached Routes: 1`、Binding `v0.3.0/v0.3.0` | PASS |
| R14 | Hostname Positive | `Host: hello.lab.test` → HTTP 200（nginx/1.27.5） | PASS |
| R15 | Hostname Negative | `Host: wrong.lab.test` → HTTP 404 | PASS |
| R16 | Scale Up | `WebService.spec.replicas 2→3`、新Job Complete、最終Deployment `3/3` | PASS |
| R17 | Scale Down | `WebService.spec.replicas 3→2`、`3/3 → 3/2 → 2/2`、最終安定 | PASS |
| R18 | Runtime Health Check（Kratix独自） | `NoHealthChecks`（`healthDefinitions: 0`） | NOT IMPLEMENTED |
| R19 | 自動CI / Registry Publish | MacでDocker Buildとkind Loadを手動実施 | NOT IMPLEMENTED |
| R20 | Team Ownership / RBAC / Rollback | 対象外、未検証 | NOT TESTED |

PASSは**当日ログの範囲内で成功を確認した項目**。別環境での同一結果や本番品質を保証しない。

## 3. 重要なログ・証跡

### 3.1 PostgreSQL Promise：ReconciledとDB Readyを区別

PostgreSQL Promise：`postgresql` Available、Resource `example` Reconciled。実行環境は次のとおり。

```text
pod/acme-org-team-a-example-postgresql-0  1/1 Running
statefulset.apps/acme-org-team-a-example-postgresql  1/1
127.0.0.1:5432 - accepting connections
postgres|postgres|1
```

解釈：KratixのReconciliation成功のみではDB機能は確認できない。Pod Ready、接続受付、認証済みSQL実行を別に検証した。PasswordなどのSecret値は記録しない。

### 3.2 v0.1.0：API契約 / Default / Validation

最初はPromiseを作成して直後に `kubectl explain` が次のエラーになった。

```text
error: couldn't find resource for "lab.platform.example.com/v1alpha1, Resource=webservices"
```

その後、CRDが利用可能となりSchema Validationが機能した。

```text
The WebService "invalid-web" is invalid:
spec.replicas: Invalid value: 99:
spec.replicas in body should be less than or equal to 5
```

`hello-web` のCRでは、`replicas` 未指定でも `replicas: 2` が現れた。CRD登録には非同期の時間差があったと解釈できるが、個別Controllerの詳細な時系列測定は未実施。

### 3.3 v0.2.0：Python Workflow / Work / Flux

```text
Generated Deployment and Service: default/hello-web
```

ResourceBindingは一時的に `DESIRED=v0.2.0`、`APPLIED=v0.1.0` となった。指定Versionへ明示的にPatchした後、Configure Job実行が観察され、最終的に：

```text
hello-web-webservice-6ac95  hello-web  webservice  v0.2.0  v0.2.0  NoHealthChecks
```

Kratix Work `webservice-hello-web-webservice-configure-6d541` と `worker-1` WorkPlacementがReady。Flux Bucket `kratix` と `kratix-workload-resources` 等のKustomizationもReady。`hello-web` Deploymentは `2/2 Ready`、ServiceはClusterIPで80/TCPを提供。

Service直接Port Forward：

```text
curl http://127.0.0.1:8082/
HTTP/1.1 200 OK
Server: nginx/1.27.5
```

### 3.4 v0.3.0：Gateway API / Hostname Routing

Gateway API `v1.5.1` Standard CRD、Traefik Helm Chart `42.2.0` / Traefik `v3.7.16` を新クラスタへ導入。

```text
GatewayClass platform-gwclass  Accepted=True
Gateway platform-gateway/shared-edge  Programmed=True
Gateway Listener web  HTTP/8000
```

PromiseにHTTPRoute生成を追加。Upgrade直後、一度 `httproute hello-web` が `NotFound`、ResourceBindingは `DESIRED=v0.3.0`・`APPLIED=v0.2.0`、Configure JobはRunningだった。その後Workloadの反映が進み、次が確認できた。

```text
hello-web-webservice-6ac95  hello-web  webservice  v0.3.0  v0.3.0  NoHealthChecks
httproute/hello-web  HOSTNAMES=["hello.lab.test"]
Gateway attachedRoutes=1
```

TraefikへのPort Forward（`8083:80`）経由のHost判定：

```text
Host: hello.lab.test
HTTP/1.1 200 OK
Server: nginx/1.27.5

Host: wrong.lab.test
HTTP/1.1 404 Not Found
```

正しいHostnameのみNginxへ到達することを示す。ただし `wrong.lab.test` の404はテナント別権限の証明ではない。

### 3.5 Day 2：Replica変更と非同期性

**Scale Up 2→3**：

```text
webservice.lab.platform.example.com/hello-web patched
job/kratix-webservice-hello-web-webservice-configure-e90a8  Complete

# 最初の確認（新しいDesired Stateの反映前）
deployment "hello-web" successfully rolled out
hello-web  2/2

# 再確認（反映後）
hello-web  3/3
```

**Scale Down 3→2**：

```text
hello-web  3/3
hello-web  3/2
hello-web  2/2
```

`kubectl rollout status` の成功は必ずしもKratix最新CRの意図したReplica数への収束を意味しない。Kratix Workflow、Kratix Work、Flux Sync、Deployment Controllerに非同期の境界があるため、Desired Stateと実測Replica数をそれぞれ検証する。

## 4. Git履歴（端末ログの確認内容）

| Commit | 主な内容 | 確認した事実 |
|---|---|---|
| `67f8125` | `kratix/webservice/` に初版のPromise、Pipeline、サンプルCRなど5ファイル | `git push origin main` 成功 |
| `14a0f3f` | HTTPRouteの追加と `kratix/gateway/shared-gateway.yaml` 作成 | `67f8125..14a0f3f main -> main` |

GitHub連携からのPrivate Repository直接取得はできておらず、以上はユーザーのターミナルログに基づく記録。SOP/RESULTS文書自体のGit Commitはこの結果に含めない。

## 5. このLabで確認できたアーキテクチャ上の知見

1. **Self-Service**：Developerは `WebService` の契約を提出するだけで、Platform実装に基づくKubernetesリソースが作成される。
2. **Inversion of Control**：Deployment / Service / HTTPRouteの実装詳細はDeveloperではなくPlatform側のWorkflowで決定する。
3. **Versioning**：Promise更新と既存Resourceの適用Versionの切替は別の処理。`Desired`/`Applied` の両方を確認する。
4. **Eventual Consistency**：Configure Job完了、Work Ready、Flux同期、Pod Readyは別の観測点。すべてが同時に変わるわけではない。
5. **CIとCDは異なる**：アプリ用のCIは未実装だが、KratixのDesired StateはSeaweedFS/Flux経由で同期できた。
6. **Role boundary**：PlatformのGateway設定は共通化できた。ただし利用者の権限・Hostname所有権を保護するには追加Policyが必要。

## 6. 未検証・制限事項

- **Health Check**：Kratixの `HealthChecksSucceeded=True` は `NoHealthChecks`。NginxのHTTP疎通は別途確認したが、SLOや継続監視は未実装。
- **IAM / RBAC / Multi-Tenant**：チーム別のKubernetes RBAC・Hostname Ownership・Admission Policy・NetworkPolicyは今回のKratixクラスタで未設定。`allowedRoutes.from: All` は安全な所有権分離を意味しない。
- **CI Build / Supply Chain**：GitHub ActionsでのPipeline Build・Test・イメージ署名・Registry Push・Digest固定は未実装。手動Docker Build / kind Loadに依存。
- **Git Source of Truth**：WebService CRの変更は `kubectl patch`。GitにWebService宣言を保存して同期する方式は未実装。
- **Runtime Feature**：HPA、Node Autoscaler、Disaster Recovery、アプリのRevision Rollback、削除フロー、SLO、可観測性を試していない。
- **再現性**：Quick Start `latest`、PostgreSQL Promise `main` の固定、クラスタ起動からの完全な再実行は今後の検証事項。
- **対象環境**：単一ローカルkind。AWS/EKSや本番のMulti-Cluster配布を検証したわけではない。

## 7. 次の研究課題

- **Lab 17**：Multi-Tenant Platform Contract。Team別Namespace/ServiceAccount/RBAC、Hostname Ownershipの検証、GatewayへのRoute接続制御、Admission Policyの組み込み。
- **CI/CD連携**：アプリ/Platform Pipelineのテストとビルド、Image Registry、宣言的なResource CR管理、Release Gateを設計する。
- **Reliability**：Promise Health Check、メトリクス、SLO、障害注入、アプリ更新・ロールバック、削除時のリソースクリーンアップを検証する。
