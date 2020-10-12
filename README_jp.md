他言語: [English](README.md)

# MoniSenForest

MoniSenForest は、モニタリングサイト 1000 プロジェクト（通称：モニ 1000、モニセン）森林・草原調査の毎木調査データやリタートラップ調査データを扱うツールです。

モニタリングサイト 1000 プロジェクトの詳細については[こちら](http://www.biodic.go.jp/moni1000/moni1000/)、森林・草原調査については[こちら](http://moni1000-forest.jwrc.or.jp)。

## 概要

MoniSenForest は、調査サイトのデータ取得者向けにデータチェックの支援や、データ利用者向けに簡単なデータの事前処理や集計・解析方法といった機能を提供することを目的として開発されています。

現在、MoniSenForest では、データのクリーニングや、植物種の和名に基づいて学名や分類学的情報を付加するといった機能を実装しています。今後のアップデートでは、簡単なデータ集計や個体群動態パラメータの推定などの機能を追加する予定です。

## 動作環境

Python 3.6 以降がインストールされていれば、どのような OS でも動作します。

以下の Python パッケージに依存しています。

- numpy
- openpyxl

## インストール

以下は、[git](https://git-scm.com) を用いたインストール方法です。`git` と `python3` がインストール済みであれば、ターミナル（Windows では、PowerShell 等をお使いください）で以下を実行することで、上記の依存パッケージも含めてインストールできます。

```bash
git clone https://github.com/MoniSenNC/MoniSenForest
cd MoniSenForest
python3 setup.py install
```

また、Python に付随しているパッケージ管理ツール`pip` を使って以下のようにインストールすることも可能です。

```bash
pip3 install git+https://github.com/MoniSenNC/MoniSenForest
```

git を用いない場合は、本リポジトリからソースコードの zip ファイルをダウンロードし、解凍してできたディレクトリ内で`python3 setup.py install`を実行してください。

### アンインストール

```bash
pip3 uninstall monisenforest
```

## 使い方

### GUI アプリケーションの起動

ターミナルで以下のコマンドを実行することで、GUI アプリケーションを起動することができます。

```bash
monisenforest
```

### Python プログラムとして使用

Python でパッケージとして呼び出して、プログラムに組み込むこともできます。

#### データの読み込み

```python
import MoniSenForest

d = MoniSenForest.read_data("path/to/datafile")
print(d.columns)  # 列名の表示
print(d.values)  # 値の表示
```

"path/to/datafile"はデータファイルのパスに置き換えてください。読み込み可能なファイル形式は、.xlsx および .csv です。

#### 列の抽出

```python
# 列名を指定して抽出
d.select_cols("spc_japan")
d.select_cols(["spc_japan", "gbh15"])

# 正規表現を利用した列抽出 (例：毎木調査データのgbh列を抽出)
d.select_cols(regex="^gbh[0-9]{2}")

# スライスによる抽出 (例：先頭から5列目までを抽出)
d[:, :5]
```

#### CSV ファイルへの書き出し

```python
d.to_csv(outpath="output.csv", keep_comments=True, cleaning=True)
```

`cleaning=True`とすることで、Unicode 文字の正規化（全角英数 → 半角英数、半角カナ → 全角カナ等）や、余分な空白・改行を削除済のデータを書き出します。

#### データチェック

```python
from MoniSenForest.datacheck import check_data

res = check_data(d)
print(res)
```

## モニタリングサイト 1000 森林・草原調査のデータセット

- **毎木調査データ** - 日本各地の 48 地点に設置された 60 調査区で実施されている毎木調査データ。最新のデータセットは [こちら](https://www.biodic.go.jp/moni1000/findings/data/index_file.html)。

- **リタートラップ調査データ** - 日本各地の 20 地点に設置された 21 調査区で実施されているリタートラップ調査データ。最新のデータセットは [こちら](https://www.biodic.go.jp/moni1000/findings/data/index_file_LitterSeed.html)。

## 参考文献

1. Ishihara MI, Suzuki SN, Nakamura M _et al._ (2011) Forest stand structure, composition, and dynamics in 34 sites over Japan. _Ecological Research_, **26**, 1007–1008. [DOI: 10.1007/s11284-011-0847-y](https://doi.org/10.1007/s11284-011-0847-y)

2. Suzuki SN, Ishihara MI, Nakamura M _et al._ (2012) Nation-wide litter fall data from 21 forests of the Monitoring Sites 1000 Project in Japan. _Ecological Research_, **27**, 989–990. [DOI: 10.1007/s11284-012-0980-2](https://doi.org/10.1007/s11284-012-0980-2)

3. [モニタリングサイト 1000 森林・草原調査 コアサイト設定・毎木調査マニュアル](http://www.biodic.go.jp/moni1000/manual/tree.pdf)

4. [モニタリングサイト 1000 森林・草原調査 落葉落枝・落下種子調査マニュアル](http://www.biodic.go.jp/moni1000/manual/litter_ver3.pdf)

## ライセンス

[MIT License](LICENSE)
