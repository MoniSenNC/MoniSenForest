## データチェック

以下は、MoniSenForest のデータチェック項目です。

### 共通のチェック項目（クラス: `MoniSenForest.datacheck.CheckDataCommon`）

| 関数名                       | 説明                                         |
| ---------------------------- | -------------------------------------------- |
| `check_invalid_date()`       | 調査日が yyyymmdd 形式になっているか         |
| `check_sp_not_in_list()`     | リストにない種和名                           |
| `check_synonym()`            | 同種が 2 つ以上の種和名で入力されていないか  |
| `check_local_name()`         | 非標準和名（check_data()では実行されません） |
| `check_blank_in_data_cols()` | 測定値に空白がないか                         |
| `check_invalid_values()`     | 測定値に無効な入力値がないか                 |
| `check_positive()`           | 測定値が正の値かどうか                       |

### 毎木データの追加チェック項目（クラス: `MoniSenForest.datacheck.CheckDataTree`）

| 関数名                       | 説明                                                                |
| ---------------------------- | ------------------------------------------------------------------- |
| `check_tag_dup()`            | タグ番号（tag_no） に重複がないか                                   |
| `check_indv_null()`          | 個体番号（indv_no）が空白(na)になっていないか                       |
| `check_sp_mismatch()`        | 同株で種が異なっていないか                                          |
| `check_mesh_xy()`            | mesh\_[xy]\_cord の入力値のチェック                                 |
| `check_stem_xy()`            | stem\_[xy]\_cord の入力値のチェック                                 |
| `check_missing()`            | 前回調査時の生存個体の記録もれがないか                              |
| `check_values_after_d()`     | d の次の入力値が na あるいは dd になっているか                      |
| `find_anomaly()`             | 成長量が基準より大きいあるいは小さい                                |
| `check_values_recruits()`    | 新規加入個体のサイズが基準より大きい                                |
| `check_values_nd()`          | nd が付いているが、前後の測定値と比較して成長量の基準に収まっている |
| `check_all(throughly=False)` | すべての項目を一括でチェック                                        |

### リターデータの追加チェック項目（クラス: `MoniSenForest.datacheck.CheckDataLitter`）

| 関数名                           | 説明                                                                                         |
| -------------------------------- | -------------------------------------------------------------------------------------------- |
| `check_trap_date_combinations()` | 同じ設置・回収日でトラップの重複・欠落がないか                                               |
| `check_installation_period1()`   | トラップ設置期間が通常より長い/短い                                                          |
| `check_installation_period2()`   | 同じ回収日で設置期間がトラップによって異なる                                                 |
| `check_installation_period3()`   | 設置日と前回の回収日のずれ                                                                   |
| `find_anomaly()`                 | 測定値の外れ値の検出（重量を対数変換後 Tukey's fences により回収日・器官ごとに外れ値を検出） |
| `check_all(throughly=False)`     | すべての項目を一括でチェック                                                                 |

### 種子データの追加チェック項目（クラス: `MoniSenForest.datacheck.CheckDataSeed`）

| 関数名                       | 説明                               |
| ---------------------------- | ---------------------------------- |
| `check_trap()`               | トラップリストとの整合性のチェック |
| `check_all(throughly=False)` | すべての項目を一括でチェック       |

> 補足：
> 
> `CheckDataTree`, `CheckDataLitter`, `CheckDataSeed`は`CheckDataCommon`のサブクラスです。
> 

### 個別項目についてチェックする場合のコード例（毎木データ）

```python
import MoniSenForest
from MoniSenForest.datacheck import CheckDataTree

d = MoniSenForest.read_data(filepath="path/to/datafile")
cd = CheckDataTree(**var(d))
res = cd.check_invalid_values()
print(res)
```
