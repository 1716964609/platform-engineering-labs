# Platform Engineering実践研究ノート
**研究日：2026年10月30〜31日**  
**環境：MacBook Air / Docker Desktop / kind / Helm / Terraform / Traefik**  
**テーマ：標準化、カスタマイズ、責務境界、マルチテナント、Golden Path**

## 1. 研究目的

開発チームが自由にアプリケーションを構築・運用できることと、Platformチームが共通の安全性・保守性を維持することを、どのように両立するかを理解する。

特に以下の仮説を考える。

**仮説：Golden Pathの適用範囲とEscape Hatchの利用条件が不明確な場合、共通化が進むほど例外処理が増え、共通基盤が複雑化したり、Platformチームへの依存が増えたりするのではないか。**

これは独立した研究仮説であり、特定企業における問題の発生を実証したものではない。

## 2. Kubernetes：アプリケーションをどのように動かすのか

### 基本構成

- **Node**：Podを動作させるマシン。今回のkindクラスタは単一Node。
- **Pod**：コンテナを実行する基本単位。
- **Deployment**：必要なReplica数を維持し、更新を管理するController。
- **Service**：Podの変化に依存しない、安定した通信入口。
- **EndpointSlice**：Serviceに対応する実際のネットワークEndpoint情報。
- **Namespace**：リソースを論理的に区切る単位。ただし、それだけで完全なセキュリティ分離にはならない。

### 実験結果

Nginxを3 Replicaでデプロイし、Service経由で30回リクエストを送った。3つのPodでリクエストが処理され、12・9・9というログ件数を確認した。

**理解したこと：Serviceは1つの固定Podではなく、変化するPod群への通信入口である。**

また、Replicaが3つあっても同じNodeで動いているため、Node障害への耐性を確認したわけではない。

## 3. Helm：Kubernetes Manifestの生成を抽象化する

### 基本構造

- `Chart.yaml`：Chartのメタデータ
- `values.yaml`：設定値とデフォルト
- `templates/`：Kubernetes Manifestのテンプレート
- `values.schema.json`：入力値の型や制約を検証する契約

Helmでは、テンプレートと設定値を組み合わせてKubernetes Manifestを生成する。

### 実験A：ライフサイクル管理

`helm install`、`helm upgrade`、`helm rollback` を実行した。

Replica数を1から3に増やし、Rollbackによって元の構成へ戻した。RollbackもReleaseの新しいRevisionとして記録される。

### 実験B：チーム別カスタマイズ

Team AとTeam Bで、同じChartを使いながら異なるReplica数を指定した。

- Team A：2 Replica
- Team B：3 Replica

同じChartを使っても、NamespaceとHelm Releaseを分ければ、アプリケーションの実行構成は独立させられる。

### 実験C：Sidecar

`sidecar.enabled` がtrueの場合だけ、BusyBoxコンテナを追加するテンプレートを作成した。

ここで、値を`hello`にしてもSidecarが生成される現象を確認した。Helmテンプレートでは、空でない文字列は条件式で真として扱われるためである。

次にJSON Schemaを追加し、Boolean以外を拒否するようにした。

**理解したこと：設定を自由に変更できることと、設定値が正しいことを保証することは別である。**

### 実験D：Library Chart

`platform-common` に共通Labelのテンプレート関数を作り、`consumer-a` と `consumer-b` から利用した。

さらにLibraryをv0.1.0からv0.2.0へ更新し、Team Aだけが新しいバージョンを利用する構成を検証した。

**理解したこと：共通ロジックの再利用はできるが、バージョンの分岐、互換性、移行管理という新たな責任が生じる。**

## 4. Terraform：共通インフラ構成をModule化する

### 基本構造

- **Module**：再利用可能なリソース定義のまとまり
- **Variable**：Moduleに渡す入力値
- **Validation**：入力条件の検証
- **Plan**：変更予定の差分表示
- **Apply**：変更の実行
- **State**：Terraformが管理するリソース状態の記録

### 実験内容

`service_contract` Moduleを作成し、Team AとTeam Bから利用した。

Hostnameについて`.lab.test`で終わるというValidationを設定した。

- `a.lab.test`：許可
- `b.lab.test`：許可
- `b2.lab.test`：Team Bのみの変更差分を表示
- `invalid.local`：Validationエラー

Team BのHostnameだけを変更したPlanでは、Team Aの変更は表示されなかった。

**理解したこと：共通Moduleのロジックと、利用チーム固有の設定値を分離できる。**

注意：今回は`terraform_data`を使用したため、実際のAWSリソースは作成していない。StateとPlanの基本を検証したLabである。

## 5. Gateway API：共通の通信入口と個別のルーティングを分離する

### 基本構造

- **GatewayClass**：Gateway実装を選択するクラス
- **Gateway**：ListenerやHTTPの入口を定義
- **HTTPRoute**：HostnameやPathとバックエンドServiceの対応を定義
- **Gateway Controller**：Gateway APIを読み取り、実際のProxyやLoad Balancerを設定

今回はGateway ControllerとしてTraefikを使用した。

### 実験A：共有Gateway

Platform側に`shared-edge`を作り、Team A・Bが自分のNamespaceにHTTPRouteを作成した。

同じ`localhost:8080`へアクセスし、HostヘッダーによりTeam A・BのServiceへ振り分けた。

Nginxのアクセスログでも、各チームのPodへの到達を確認した。

### 実験B：独立したRoute変更

Team BのHostnameを`b.lab.test`から`b2.lab.test`へ変更した。

その結果：

| Hostname | HTTP |
|---|---|
| a.lab.test | 200 |
| b.lab.test | 404 |
| b2.lab.test | 200 |
| c.lab.test | 404 |

GatewayのGenerationは1のまま、Team BのHTTPRouteだけが更新された。

**理解したこと：Gatewayそのものを変更せずに、開発チーム側のRouteを変更できる。**

ただし今回はローカルのTraefikであり、AWS ALBを実際に構築したわけではない。

## 6. マルチテナント：Namespaceの許可だけでは不十分

### 実験A：未許可Namespaceの拒否

Gatewayの`allowedRoutes`にNamespace Labelによる条件を設定した。

Team Cは許可Labelを持っていなかったため、HTTPRouteを作成してもGatewayから拒否された。

- `Accepted=False`
- `Reason=NotAllowedByListeners`
- `ResolvedRefs=True`

**理解したこと：参照先のServiceが存在していても、そのRouteがGatewayに接続できるとは限らない。**

### 実験B：Hostnameの所有権

Gatewayの利用を許可されているTeam Aから、`c.lab.test`のHTTPRouteを作成した。

結果は`Accepted=True`、HTTP 200。

**理解したこと：Namespace単位の接続許可は、Hostname単位の所有権を保証しない。**

検証後、実験用HTTPRouteは削除した。

## 7. RBACとAdmission Policy：操作権限と設定内容を分けて制御する

### RBAC

Team AのServiceAccountに、Team AのHTTPRouteを操作するRoleを付与した。

認可結果：

- Team AのHTTPRoute作成：yes
- Team BのHTTPRoute作成：no
- PlatformのGateway変更：no
- Namespace変更：no

### ValidatingAdmissionPolicy

CELを利用し、Team Aは`a.lab.test`、Team Bは`b2.lab.test`のみ指定可能とした。

Server Dry Runで以下を確認した。

- 許可Hostname：作成可能
- 他チーム用Hostname：Admissionによる拒否

**理解したこと：RBACは誰がどのリソースを操作できるかを決め、Admission Policyはそのリソースの内容が規則に適合するかを決める。**

注意：これは単純化した固定HostnameのLabであり、本番向けの完全なマルチテナントセキュリティ設計ではない。

## 8. 実験中に見つかった注意点

### 宣言ファイルとクラスタの状態

`kubectl patch`で変更したHostnameと、元の`routes.yaml`が一致しない状態になった。

ファイルを再適用すると、その宣言内容がクラスタに反映された。最終的に`routes.yaml`を`b2.lab.test`へ更新し、再適用後も期待する通信状態を維持できた。

これはGitOpsで扱うDesired StateとActual Stateの関係を理解する入り口になった。

### Gateway APIのCRDバージョン

v1.6.3を導入後、古いv1.5.1のCRD適用を試み、Admission Policyによって拒否された。

これはアプリケーションのHTTP転送エラーではなく、クラスタAPI定義のバージョン管理に関わる問題だった。

## 9. Platform Engineeringとして内部化したこと

今回の実験から得られる暫定的な設計原則は次のとおり。

1. **所有権と変更能力は別**：リポジトリやChartを開発チームに渡すだけではセルフサービスは完成しない。
2. **共通化には維持コストがある**：LibraryやModuleを増やすほど、依存バージョンと互換性の管理が必要になる。
3. **操作可能な範囲と設定内容の制約は別**：RBACだけではHostname所有権を制御できない。
4. **変更頻度と責務を対応させる**：頻繁に変わるルーティングを、毎回Platformの変更フローに通すのが適切とは限らない。
5. **Escape Hatchは無制限の例外ではない**：拡張可能な範囲、責任者、検証方法、共通機能へ取り込む条件を決める必要がある。
6. **抽象化の目的は複雑さを隠すことだけではない**：誰が何を理解し、何を変更し、何に責任を持つかを整理することが重要。

## 10. 研究の限界

今回のPoCでは、以下はまだ検証していない。

- 実AWSのALB、ACM、IAM、EKSとの統合
- Argo CDによるGitOpsの自動同期
- AppProjectによるGitリポジトリ・クラスタ・Namespace単位の制限
- CI Workflowの共通化と個別拡張
- External Secrets OperatorによるSecret同期
- 複数の独立したKubernetesクラスタでの権限分離
- チーム別サブドメインの動的委譲
- 大規模運用での性能、保守工数、開発者体験

## 11. 次の研究仮説

**仮説A：CI/CDの共通化でも、Helmと同様の過剰カスタマイズ問題が発生するのではないか。**

**仮説B：Argo CDで複数クラスタを一元管理すると、Gitソース、デプロイ先、操作権限の境界設計が複雑化するのではないか。**

**仮説C：Golden PathとEscape Hatchの責務境界を明文化し、例外を標準機能へ昇格させる基準を用意すれば、Platformチームへの依頼を減らせるのではないか。**

いずれも、実験によって検証していく研究仮説である。

---

### 参考資料

- ギフティ『プラットフォームエンジニアリングことはじめ』（2025年11月）
  https://speakerdeck.com/jmakk0301/gihuteiniokeru-puratutohuomuenziniaringukotohazime
- ギフティ『引いては引き直す Kubernetes運用における境界設計とその見直し』（2026年6月）
  https://speakerdeck.com/jmakk0301/yin-itehayin-kizhi-su-kubernetesyun-yong-niokerujing-jie-she-ji-tosonojian-zhi-si
- Gateway API Security
  https://gateway-api.sigs.k8s.io/docs/concepts/security/
- Argo CD Projects
  https://argo-cd.readthedocs.io/en/stable/user-guide/projects/
