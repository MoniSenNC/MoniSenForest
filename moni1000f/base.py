import json
import re
import unicodedata
from datetime import datetime as dt
from pathlib import Path
from typing import List, Union

import pandas as pd
import xlrd

# fd = Path(__file__).resolve().parents[0]
# fd = Path("moni1000f/")


class MS1KDataFrame(pd.DataFrame):
    """Subclassed pd.DataFrame with additional metadata."""

    _metadata = ["plot_id", "data_type"]

    @property
    def _constructor(self):
        return MS1KDataFrame


def guess_data_type(df):
    """Guess data type."""
    tree_col_req = [
        "tag_no",
        "indv_no",
        "spc_japan",
        "^gbh[0-9]{2}$",
        "^s_date[0-9]{2}$",
    ]

    litter_col_req = [
        "^trap_id$",
        "^s_date1$",
        "^s_date2$",
        "^wdry_",
        "^w_",
    ]

    seed_col_req = [
        "^trap_id$",
        "^s_date1$",
        "^s_date2$",
        "^w",
        "^spc$",
        "^status$",
        "^form$",
    ]

    if all([any(df.columns.str.contains(c)) for c in tree_col_req]):
        data_type = "tree"
    elif all([any(df.columns.str.contains(c)) for c in litter_col_req]):
        data_type = "litter"
    elif all([any(df.columns.str.contains(c)) for c in seed_col_req]):
        data_type = "seed"
    else:
        data_type = "other"

    return data_type


def read_data(filepath, *args, **kwargs):
    """Read the Moni1000 data file and make a DataFrame object."""
    filepath = Path(filepath)

    df = MS1KDataFrame(read_file(filepath, *args, **kwargs))
    df.data_type = guess_data_type(df)

    forest_type = ["AT", "EC", "BC", "EB", "DB"]
    pat_plotid = re.compile("|".join(
        ["[A-Z]{{2}}-{}[0-9]".format(i) for i in forest_type]))
    m = pat_plotid.search(filepath.name)
    if m:
        df.plot_id = m.group()

    return df


def read_file(filepath: Union[str, Path], *args, **kwargs) -> pd.DataFrame:
    """
    Read Excel/CSV files and return a pd.DataFrame object.

    デフォルトでは全て文字列として読み込み、空白セルのみNaN
    として扱う（naやNAは文字列）

    Parameters
    ----------
    filepath : str
        The path to the excel or csv file

    See Also
    ----------
    pandas.DataFrmae
    pandas.DataFrame.read_csv
    pandas.DataFrame.read_excel
    """
    filepath = Path(filepath)

    if "dtype" not in kwargs:
        kwargs["dtype"] = str
    if "na_values" not in kwargs:
        kwargs["na_values"] = ""
    if "keep_default_na" not in kwargs:
        kwargs["keep_default_na"] = False
    if "comment" not in kwargs:
        kwargs["comment"] = "#"

    if filepath.suffix in [".xlsx", ".xls"]:
        if "sheet_name" not in kwargs:
            wb = xlrd.open_workbook(filepath)
            # シート名が与えられていなければ"Data"を探し読み込む
            # "Data"シートなければ1枚目のシートを読み込む
            try:
                kwargs["sheet_name"] = wb.sheet_names().index("Data")
            except ValueError:
                kwargs["sheet_name"] = 0
        return pd.read_excel(filepath, *args, **kwargs)
    elif filepath.suffix in [".csv"]:
        return pd.read_csv(filepath, *args, **kwargs)
    else:
        raise RuntimeError("Input file must be the csv or excel format")


def read_json(filepath):
    with open(filepath) as f:
        d = json.load(f)
    return (d)


def file_to_csv(filepath: str, outdir: str = None):
    """
    Excel/CSVファイルを読み込み、クリーニング後、CSVファイルとして書き出す.

    Parameters
    ----------
    filepath : str
        The path to the excel or csv file

    outdir : str, default None
        Output directory
    """
    filepath = Path(filepath)

    if outdir:
        outdir = Path(outdir)
        outdir.mkdir(parents=True, exist_ok=True)
    else:
        outdir = filepath.parent

    basename = filepath.stem
    outpath = outdir.joinpath(basename + ".csv")

    df = read_file(filepath, comment=None, header=None)
    df = clean_data_frame(df)
    df.to_csv(outpath, header=False, index=False)


def clean_data_frame(df, drop_na=True, verbose=False):
    """データのクリーンアップ."""
    res = df.copy()
    nrow0, ncol0 = res.shape
    # Excelの浮動小数点計算精度で長くなっている値を丸める
    res = res.applymap(clean_float)
    # 日付がdatetime型になっている要素をyyyymmddの文字列に変換
    res = res.applymap(datetime_to_yyyymmdd)
    # 半角文字を全角に変換
    res = res.applymap(normalize_chrs)
    # セル内改行、タブ、垂直タブ、改頁を削除
    res = res.replace("\r\n|\n|\r|\t|\x0b|\x0c", "", regex=True)
    # 空白行・列を削除
    if drop_na:
        res = res.dropna(how="all", axis=1).dropna(how="all", axis=0)
        nrow1, ncol1 = res.shape
        dropped = nrow0 - nrow1, ncol0 - ncol1

        if sum(dropped) > 0 and verbose:
            msg = "Dropped some empty row(s) and/or colmun(s): "
            msg += "({})".format(", ".join([str(i) for i in dropped]))
            print(msg)

    return res


def normalize_chrs(x):
    """Unicode文字の標準化."""
    if isinstance(x, str):
        return unicodedata.normalize("NFKC", x)
    else:
        return x


def clean_float(x):
    """小数点以下が長い場合は丸める."""
    pat = re.compile(r"(\d*\.\d{14,})")
    m = pat.match(str(x))
    if m:
        return "{:.3f}".format(float(m.group(0))).rstrip("0")
    else:
        return x


def datetime_to_yyyymmdd(x):
    """日付がyyyymmddになっていない場合修正."""
    pat_datetime = re.compile(r"(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})")
    m = pat_datetime.match(str(x))
    if m:
        return dt.strftime(dt.strptime(m.group(1), "%Y-%m-%d %H:%M:%S"), "%Y%m%d")
    else:
        return x
