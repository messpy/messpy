# messpy

Catch maintainability problems in Python before they calcify: oversized functions and classes, tangled dependencies, dead private code, muddy naming, and other mess that reviews keep rediscovering.

`messpy` is a local CLI. It reads source as text, never imports or runs your project, and needs no project dependencies installed. Python 3.11+.

## Quick start

```console
python -m pip install messpy
messpy src text python --ignore-tests
```

That scans `src` with the recommended low-noise policy and prints findings on stdout. Exit `0` is clean, `2` means findings, `1` means the tool or a source file failed.

Common next steps:

```console
messpy src text python,opinionated --ignore-tests
messpy src sarif python --ignore-tests --reportfile reports/messpy.sarif
messpy src github python --ignore-tests
```

Full command syntax, options, and discovery: [docs/usage.md](https://github.com/quality-gates/messpy/blob/main/docs/usage.md).
What each rule checks: [docs/rules.md](https://github.com/quality-gates/messpy/blob/main/docs/rules.md).
Machine-readable report shapes: [docs/reports.md](https://github.com/quality-gates/messpy/blob/main/docs/reports.md).

## Install

With Homebrew (standalone executable; Python is not required):

```console
brew install quality-gates/tap/messpy
messpy --version
```

Or install the Python package:

```console
python -m pip install messpy
# or: pipx install messpy
# or: uv tool install messpy
messpy --version
```

## Tune the gate

Start with `python`. Add `opinionated` when you want the stricter checks the recommended set leaves out. Point at a custom XML ruleset when thresholds or membership need to live in the repo:

```xml
<ruleset name="team policy">
  <rule ref="python">
    <exclude name="DevelopmentCodeFragment" />
  </rule>
  <rule ref="LongVariable">
    <priority>2</priority>
    <properties>
      <property name="maximum" value="50" />
    </properties>
  </rule>
</ruleset>
```

```console
messpy src text path/to/team-policy.xml --ignore-tests
```

## Suppress one intentional exception

```python
# messpy-disable-next-line RuleName
value = deliberate_exception()
```

Region form: `messpy-disable` / `messpy-enable`. Names are case-insensitive. `--strict` keeps suppressed findings visible in the report.

## Drop it into CI

```yaml
# GitHub Actions
- run: pip install messpy
- run: messpy src github python --ignore-tests
```

```yaml
# GitLab Code Quality
script: messpy src gitlab python --reportfile gl-code-quality-report.json
artifacts:
  reports:
    codequality: gl-code-quality-report.json
```

## Maintainers

Release process: [docs/releasing.md](https://github.com/quality-gates/messpy/blob/main/docs/releasing.md). Fuzzing: [docs/fuzzing.md](https://github.com/quality-gates/messpy/blob/main/docs/fuzzing.md).

## olm-lite

このリポジトリには、AIを必須にしない軽量CLI `olm` も含まれます。起動時に引数からモードを判定し、ローカルのJSONL履歴へ実行結果を保存します。検索は外部サービスを使わず、過去の出力との語彙類似度で行います。

```console
olm                 # 現在のディレクトリを解析
olm path/to/file    # ファイルの構造を解析
olm history --last 20
olm history --failed --grep permission
olm --ai            # Ollama未設定なら自動的にローカル検索へフォールバック
```

コマンド文字列は提案として表示し、対話的な確認なしには実行しません。`rm`、`dd`、`mkfs`、権限変更などの危険な操作は提案のみで停止します。履歴は `XDG_STATE_HOME` があればその配下、なければ `~/.local/state/olm-lite/history.jsonl` に保存されます。
