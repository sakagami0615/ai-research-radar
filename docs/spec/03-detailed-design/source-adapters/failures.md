# リトライと取得制約

旧設計書の該当節を分割した資料。現行と移行目標の区別は [文書全体の入口](../../../README.md) から確認する。

## リトライ方針

一時的な障害(429 Too Many Requests、5xx系)のみ最大3回まで指数バックオフでリトライする(`Retry-After`ヘッダーがあれば尊重)。403/404/406などの恒久的なエラーは即座に失敗させ、無駄なリトライを行わない。

OpenAlexは環境変数 `AI_RADAR_OPENALEX_MAILTO` にcontact先メールアドレスを設定すると、リクエストに`mailto`パラメータを付与し、OpenAlex側のpolite pool(レート制限が緩いプール)を利用できる。個人のメールアドレスをリポジトリに埋め込まないための設計であり、未設定時は付与しない。


## 注意点

- 複数endpointを持つSource(`official_blogs` / `huggingface_orgs`)の部分失敗は、Adapterの `partial_errors` に溜め、`collect` / `daily` がerrorsへ転記する。
- Sourceの累積指標をそのままHOT scoreに使わない。
- GitHub stars、npm search score、PyPI keyword strengthなどはSource内で正規化する。
- RSS/Atom形式は提供側変更に弱いため、実運用では定期的なsmoke testを行う。
- Sourceが完全に収集失敗した場合(0件かつSource単位エラーあり)、日次レポートの「データ欠落」セクションに自動的に明示される。arxivの406はこのプロジェクトのネットワーク環境固有のCDN/IPレベルのブロックであり、ヘッダーやリトライでは解決しないことを確認済み。
