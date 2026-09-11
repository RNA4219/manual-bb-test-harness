# Release Policy

## Versioning

Use semantic versions for the Skill repository.

- Patch: wording fixes, typo fixes, validator fixes that do not change expected behavior.
- Minor: new domain packs, new references, new golden examples, stricter evaluation guidance.
- Major: changed artifact contract, renamed skill, or incompatible output ordering.

## Release Checklist

- `scripts/validate-skill.ps1` passes.
- `scripts/quick-validate-skill.py skills/manual-bb-test-harness` passes.
- Golden examples still represent current expected behavior.
- `README.md` points to new references or schemas.
- Forward-test report is added or updated when behavior changes materially.

## Compatibility Rules

- Do not rename the skill folder without a major version.
- Do not remove artifact fields without a major version.
- Prefer adding optional fields before making them required.
- Keep `SKILL.md` concise and move detailed behavior into `references/`.

## PyPI公開仕様

パッケージ名は`bb-harness`。GitHub Releaseに添付したwheelとsdistを、
検証後に同じバイト列のままPyPIへ公開する。公開済みタグ・配布物は作り直さない。

| id | 要件 |
|---|---|
| PUB-1 | `publish-pypi.yml`をmainから手動起動し、既存の正式版タグ`vX.Y.Z`を指定する。タグのコミットはmainに含まれること |
| PUB-2 | 公開workflowのコミットとタグのコミットについて、mainの最新validate runが完了・successであること。HATE/QEGを含む既存CI条件を維持する |
| PUB-3 | 正式なGitHub Releaseからwheel、sdist、`SHA256SUMS.txt`を取得する。欠落・重複・余分なchecksum項目・hash不一致・パッケージ名/版不一致・ライセンス不足は公開前に失敗する |
| PUB-4 | 取得したwheelとsdistを隔離環境へインストールし、既存CLI smokeを完走する。検証済みの2ファイルだけを公開ジョブへ渡す |
| PUB-5 | PyPI Trusted Publisherを`RNA4219/manual-bb-test-harness`、workflow `publish-pypi.yml`、environment `pypi`へ限定する。GitHubの同environmentはmainのみ許可する |
| PUB-6 | OIDCの`id-token: write`は公開ジョブだけに付け、長期API tokenを保存しない。ActionはコミットSHAで固定する |
| PUB-7 | 公開後はPyPIのversion・2ファイルのSHA-256と、PyPIからの隔離インストールを確認する。同版の再公開は自動skipせず停止し、失敗時は公開状態を確認してから対応する |
| PUB-8 | PyPAの`trove-classifiers`と照合し、未登録または`Private ::`で始まる分類をbuild・公開前に拒否する。検証依存はdevだけに追加する |

PyPIアカウントのメール確認・2FAとPending Trusted Publisherを初回公開前に設定する。
Pending Publisherは初回公開時にプロジェクトのPublisherへ切り替わる。
設定手順は[PyPI公式文書](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/)を参照する。

```powershell
gh workflow run publish-pypi.yml --ref main -f tag=v4.0.1
```

受入では、正常な配布物、改変・欠測・版不一致の拒否、追加workflowを含む緑CI、
実PyPI公開および公開後の照合を確認する。今回の変更は配布経路の追加であり、
既存の4.0.0パッケージの内容・バージョンは変えない。

### 4.0.1: PyPIメタデータの修正

初回4.0.0公開は、未登録classifier `Intended Audience :: Quality Assurance`により
PyPIがHTTP 400で拒否した。PyPIのプロジェクト未作成（HTTP 404）を確認済み。
この分類を除去し、分類辞書に基づく検証を追加して4.0.1を発行する。
README・CLI・関連文書の現行版を同期し、4.0.0のGitHub Releaseは保持する。
実装・artifact契約・ライセンスの挙動は変えず、緑CI後に新規タグから配布物を作成する。
