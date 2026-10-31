# Lab 16 — Kratix Platform Contract / GitOps / Gateway API

## 1. 目的

開発者が `WebService` Custom Resource（CR）の `image`、`replicas`、`hostname` を宣言するだけで、Platform側が Deployment / Service / HTTPRoute を生成・反映し、アプリケーションの構成変更に追従することを検証する。

本Labは **Internal Developer Platform（IDP）の最小PoC** であり、本番運用基盤ではない。Kratix、SeaweedFS、Flux、Kubernetes、Traefikを使う。アプリケーションのCIやクラスタ・ノードの自動払い出しは対象外。

## 2. 前提・環境

- 実験日：2026-10-31（JST）。検証結果は `RESULTS.md` を参照。
- ローカル：macOS、Docker Desktop、`kind`、`kubectl`、`helm`、`python3`。
- 実験用Kubernetesクラスタ：`kind-kratix-lab`（コンテキスト）。既存の `kind-helm-lab` とは別環境。
- Kratix：Quick Start installer（実験時に `latest` URLを使用。**バージョン固定なし**）。
- State Store：SeaweedFS Bucket。GitOps Controller：Flux CD。
- Gateway API CRD：`v1.5.1` Standard install。
- Traefik Helm Chart：`42.2.0`、アプリケーション：`v3.7.16`。
- Custom Promise：`webservice`、最終検証版 `v0.3.0`。
- Pipeline Image：`kratix-webservice-pipeline:v0.3.0`（ローカルビルドしてkindへロード）。
- PostgreSQL Promise（参考実験）：`syntasso/promise-postgresql` の `main`、ログ時点 `v1.0.0-beta.5`（参照ブランチは**固定なし**）。

### 2.1 リポジトリ内のファイル

```text
kratix/
├── gateway/
│   └── shared-gateway.yaml
└── webservice/
    ├── example-resource.yaml
    ├── invalid-resource.yaml
    ├── promise.yaml
    └── pipeline/
        ├── Dockerfile
        └── render.py
```

**再現手順はリポジトリにある最終版 `promise.yaml`（v0.3.0）と `render.py` を前提とする。** v0.1.0 → v0.2.0 → v0.3.0 の更新履歴は `RESULTS.md` にまとめる。

## 3. 全体構成

```text
Developer
  └─ kubectl apply WebService CR (image / replicas / hostname)
      └─ Kubernetes API / Kratix Promise + Resource Configure Workflow
          └─ Pipelineコンテナ (Python: /kratix/input/object.yaml を読む)
              └─ /kratix/output/{deployment,service,httproute}.yaml
                  └─ Kratix Work / WorkPlacement
                      └─ SeaweedFS Bucket (State Store)
                          └─ Flux Bucket Source + Kustomization
                              └─ Kubernetes Deployment / Service / HTTPRoute
                                  └─ Traefik Shared Gateway → Nginx Pods
```

この構成では、開発者側の `WebService` CRは **Kubernetes API上で管理**し、生成物を **SeaweedFS → Flux** で同期する。GitHub PushだけでWebServiceが更新される構成ではない。

## 4. 再現手順：基盤の準備

> コマンドはすべてリポジトリのルートで実行する。作業対象の取り違えを避けるため、`kubectl` / `helm` では対象コンテキストを明示する。以下にコメント行を含むため、zshで必要なら `setopt interactivecomments` を実行する。

### 4.1 kindクラスタ作成（新規環境のみ）

```bash
kind create cluster --name kratix-lab
kubectl --context kind-kratix-lab get nodes
cd ~/platform-engineering-labs
```

既に同名クラスタがあるときは再作成しない。既存の `kind-helm-lab` は変更しない。

### 4.2 Kratix Quick Startのインストール

```bash
kubectl --context kind-kratix-lab apply \
  -f https://github.com/syntasso/kratix/releases/download/latest/kratix-quick-start-installer.yaml

kubectl --context kind-kratix-lab logs \
  -n default -f job/kratix-quick-start-installer

kubectl --context kind-kratix-lab get pods -A
kubectl --context kind-kratix-lab get promises
kubectl --context kind-kratix-lab get destinations
```

期待：インストーラが `Kratix installation complete!` を報告し、Kratix Controller、Flux Controllers、SeaweedFSが起動、Destination `worker-1` がReady。Quick StartのURLは可変なので、厳密な再現が必要な場合は採用したリリースとManifestを別途固定すること。

### 4.3 Gateway API CRDとTraefik

```bash
kubectl --context kind-kratix-lab apply --server-side \
  -f https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.5.1/standard-install.yaml

kubectl --context kind-kratix-lab get crds | grep gateway.networking.k8s.io

helm repo add traefik https://traefik.github.io/charts
helm repo update

helm upgrade --install edge traefik/traefik \
  --kube-context kind-kratix-lab \
  --namespace platform-gateway \
  --create-namespace \
  --version 42.2.0 \
  --set providers.kubernetesGateway.enabled=true \
  --set gateway.enabled=false \
  --set gatewayClass.enabled=false \
  --wait \
  --timeout 300s

kubectl --context kind-kratix-lab apply \
  -f kratix/gateway/shared-gateway.yaml

kubectl --context kind-kratix-lab get gatewayclasses,gateways -A
kubectl --context kind-kratix-lab -n platform-gateway \
  describe gateway shared-edge
```

共有Gateway `platform-gateway/shared-edge` の `web` ListenerはHTTP/8000。`allowedRoutes.namespaces.from: All` のため他NamespaceからのRoute接続を許すが、**これだけではテナント別Hostname所有権を保護しない**。`GatewayClass Accepted=True`、`Gateway Programmed=True` が目安。

kind環境のTraefik Serviceは `LoadBalancer` の `EXTERNAL-IP=<pending>` となることがある。本LabはPort Forwardを使用するため、外部IPを必須条件にしない。

## 5. 再現手順：WebService Promise

### 5.1 Pipelineコンテナをビルド・kindにロード

```bash
cd ~/platform-engineering-labs
python3 -m py_compile kratix/webservice/pipeline/render.py

docker build \
  -t kratix-webservice-pipeline:v0.3.0 \
  kratix/webservice/pipeline

kind load docker-image kratix-webservice-pipeline:v0.3.0 \
  --name kratix-lab
```

`render.py` は `WebService` CRを読み、Deployment、Service、HTTPRouteを生成する。`Dockerfile` は Python 3.12 Alpine とPyYAMLを使用。PromiseのPipelineには `imagePullPolicy: Never` が設定されているため、**クラスタ再作成時にはローカルImageを再度ロードする必要がある**。CI Build / Registry Push / Digest Pinningは未実装。

### 5.2 Promise登録

```bash
kubectl --context kind-kratix-lab apply --dry-run=server \
  -f kratix/webservice/promise.yaml

kubectl --context kind-kratix-lab apply \
  -f kratix/webservice/promise.yaml

kubectl --context kind-kratix-lab get promises
kubectl --context kind-kratix-lab get promiserevisions
kubectl --context kind-kratix-lab explain \
  webservices.lab.platform.example.com.spec
```

期待：`webservice` が `Available`、バージョン `v0.3.0`。CRDの登録はPromiseの登録と**非同期**である。直後の `kubectl explain` が `couldn't find resource` になる場合は、CRDの登録を確認して再試行する。

API契約：`image`・`hostname` は必須、`replicas` は整数1〜5、デフォルト2。`hostname` は当該PoCでは長さ制約のみで、正しいFQDN形式や所有権の保証はない。

### 5.3 Schema Validation（失敗が正しいテスト）

```bash
kubectl --context kind-kratix-lab apply --dry-run=server \
  -f kratix/webservice/invalid-resource.yaml
```

`replicas: 99` が最大値5を超えるため **Invalid** が期待結果。エラーにならない場合はCRDのSchemaと適用先コンテキストを確認する。

### 5.4 正常なWebServiceを作成

```bash
kubectl --context kind-kratix-lab apply \
  -f kratix/webservice/example-resource.yaml

kubectl --context kind-kratix-lab -n default \
  get webservice hello-web -o yaml

kubectl --context kind-kratix-lab -n default \
  get jobs,resourcebindings,works,workplacements

kubectl --context kind-kratix-lab -n default \
  get deployments,services,httproutes

kubectl --context kind-kratix-lab -n flux-system \
  get buckets,kustomizations
```

`example-resource.yaml` では `replicas` を省略している。取得結果では `spec.replicas: 2` が期待される。Configure Workflowが起動し、Work/WorkPlacementとFluxが同期すると、`hello-web` Deployment、Service、HTTPRouteが生成される。

**注意：** PipelineのJobが `Complete` になっても、その直後にDeploymentやHTTPRouteが見つからない場合がある。Kratix Work → Bucket → Flux → Kubernetesは非同期。後続リソースの反映まで再確認する。`kubectl rollout status` は、まだ旧Replica数のDesired Stateしか適用されていない時点でも成功し得る。

### 5.5 Hostnameルーティングの実動作

ターミナルA（起動したまま）：

```bash
kubectl --context kind-kratix-lab -n platform-gateway \
  port-forward svc/edge-traefik 8083:80
```

ターミナルB：

```bash
curl -i --max-time 10 \
  -H 'Host: hello.lab.test' \
  http://127.0.0.1:8083/

curl -i --max-time 10 \
  -H 'Host: wrong.lab.test' \
  http://127.0.0.1:8083/

kubectl --context kind-kratix-lab -n default \
  describe httproute hello-web
kubectl --context kind-kratix-lab -n platform-gateway \
  get gateway shared-edge \
  -o jsonpath='{.status.listeners[0].attachedRoutes}{"\n"}'
```

期待：正しいHostで `HTTP/1.1 200 OK`（nginx）、異なるHostで `404 Not Found`。後者は本Lab以外に一致するRouteがないことが前提。Port Forwardは不要になったら `Ctrl+C` で終了する。

## 6. 再現手順：Day 2 Operations

### 6.1 Scale Up（2 → 3）

```bash
kubectl --context kind-kratix-lab -n default \
  patch webservice hello-web --type=merge \
  -p '{"spec":{"replicas":3}}'

kubectl --context kind-kratix-lab -n default \
  get jobs
kubectl --context kind-kratix-lab -n default \
  get deployment hello-web -w
```

別ターミナルで `kubectl --context kind-kratix-lab -n default get pods -l app=hello-web` を実行し、3つのPodがReadyになることを確認する。`-w` は `Ctrl+C` で終了する。

### 6.2 Scale Down（3 → 2）

```bash
kubectl --context kind-kratix-lab -n default \
  patch webservice hello-web --type=merge \
  -p '{"spec":{"replicas":2}}'

kubectl --context kind-kratix-lab -n default \
  get deployment hello-web -w
```

期待：`3/3 → 3/2 → 2/2` などの中間状態を経て、`spec.replicas=2`、`status.readyReplicas=2` へ収束する。これは**宣言的な構成変更**であり、Deployment Revisionを選択するアプリケーションのロールバックではない。またHPAやNode Autoscalingを実装したわけでもない。

### 6.3 最終状態の確認

```bash
kubectl --context kind-kratix-lab -n default \
  get webservice hello-web -o yaml
kubectl --context kind-kratix-lab -n default \
  get resourcebindings
kubectl --context kind-kratix-lab -n default \
  get deployments,services,httproutes,pods -l app=hello-web
kubectl --context kind-kratix-lab -n flux-system \
  get buckets,kustomizations
```

※ 最後の `-l app=hello-web` は、Deployment/Service/HTTPRouteに同一Labelがない場合それらの表示を絞り込む。必要に応じて `get deployments,services,httproutes` と `get pods -l app=hello-web` を別々に実行する。

## 7. Promise Revisionを更新する場合の注意点

最初の実験ではv0.1.0（Schemaのみ）→v0.2.0（Deployment/Service生成）→v0.3.0（HTTPRoute生成）と更新した。既存Resourceの `ResourceBinding` が `desired=latest` でも `applied` が旧バージョンのまま一時的に残った。手動で対象Revisionを明示して更新し、新しいWorkflowが実行された。

`ResourceBinding` の名前には生成サフィックスが付くため、再現環境で次のように確認してから対象を指定すること。

```bash
kubectl --context kind-kratix-lab -n default get resourcebindings
kubectl --context kind-kratix-lab get promiserevisions \
  -l kratix.io/promise-name=webservice --show-labels
```

手動アップグレード例（**当日ログの名前を使用した例**。新しい環境では名前を読み替える）：

```bash
kubectl --context kind-kratix-lab -n default \
  patch resourcebinding hello-web-webservice-6ac95 \
  --type=merge \
  -p '{"spec":{"version":"v0.3.0"}}'
```

`Desired`・`Applied` 両方がv0.3.0になったこと、Configure Workflowが成功したこと、最終Manifestが反映されたことを別々に確認する。

## 8. 参考：PostgreSQL Promiseの疎通確認（独立したサブ実験）

同じクラスタで、既存PostgreSQL Promiseのセルフサービス構築も検証した。

```bash
kubectl --context kind-kratix-lab apply \
  -f https://raw.githubusercontent.com/syntasso/promise-postgresql/refs/heads/main/promise.yaml

kubectl --context kind-kratix-lab apply -f - <<'YAML'
apiVersion: marketplace.kratix.io/v1alpha2
kind: postgresql
metadata:
  name: example
  namespace: default
spec:
  teamId: "acme-org-team-a"
YAML

kubectl --context kind-kratix-lab -n default \
  wait --for=condition=Ready \
  pod/acme-org-team-a-example-postgresql-0 --timeout=180s

kubectl --context kind-kratix-lab -n default \
  exec acme-org-team-a-example-postgresql-0 \
  -- pg_isready -h 127.0.0.1 -p 5432
```

SQL疎通の際はOperator生成Secretを使用する。**パスワードを画面・Git・研究記録に保存しない。** 次の例では標準入力でコンテナへ渡し、変数を削除する。

```bash
DB_PASSWORD=$(
  kubectl --context kind-kratix-lab -n default get secret \
    postgres.acme-org-team-a-example-postgresql.credentials.postgresql.acid.zalan.do \
    -o jsonpath='{.data.password}' | base64 -d
)

printf '%s\n' "$DB_PASSWORD" |
  kubectl --context kind-kratix-lab -n default exec -i \
    acme-org-team-a-example-postgresql-0 -- sh -c '
      read -r PGPASSWORD
      export PGPASSWORD
      exec psql -h 127.0.0.1 -U postgres -d postgres \
        -v ON_ERROR_STOP=1 -Atc \
        "SELECT current_user, current_database(), 1;"
    '

unset DB_PASSWORD
```

当日実測：`postgres|postgres|1`。このサブ実験のPostgreSQL PromiseにはHealth Checkがなく、`Reconciled=True` だけではSQL動作を証明できないため、別途SQLテストを実施した。

## 9. 制約・後続Labへの課題

1. `NoHealthChecks`：Kratix Promise自体のRuntime Health Checkは未定義。Kubernetes PodのReadyとHTTP疎通を別検証している。
2. **認可・マルチテナント**：Namespace/Hostnameの所有権、チーム別RBAC、Admission Policyはこのクラスタで未実装。`allowedRoutes.from: All` は隔離の代替ではない。
3. **CI/CDの範囲**：CIは手動Docker Build。CDはFluxがSeaweedFSから同期。GitHub ActionsとWebServiceの自動連携なし。
4. **再現性**：Kratix installerの`latest`、PostgreSQL Promiseの`main`、ローカルImageの手動Loadが再現性リスク。リリース・依存関係・Digestの固定が必要。
5. **スケールと復旧**：手動指定Replica数の変更のみ。HPA、Node Autoscaling、障害注入、正規のApplication Rollback、削除・解約ライフサイクルは未検証。
6. **環境区分**：実験用kind単一ノード。EKS/複数クラスタ/本番アクセス制御等を検証したものではない。
