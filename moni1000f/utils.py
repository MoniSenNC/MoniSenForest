import re
import unicodedata
from datetime import datetime as dt
from pathlib import Path

import pandas as pd
import xlrd


def read_file(filepath: str, *args, **kwargs):
    """
    Excel/CSVファイルの読み込んでDataFrameオブジェクトを返す
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
            # シート名"Data"を探して読み込む（なければ1枚目のシート）
            try:
                kwargs["sheet_name"] = wb.sheet_names().index("Data")
            except ValueError:
                kwargs["sheet_name"] = 0
        return pd.read_excel(filepath, *args, **kwargs)
    elif filepath.suffix in [".csv"]:
        return pd.read_csv(filepath, *args, **kwargs)
    else:
        raise RuntimeError("Input file must be the csv or excel format")


def file_to_csv(filepath, outdir=None):
    """
    Excel/CSVファイルを読み込み、クリーニング後、CSVファイルとして書き出す

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

    # データの読み込み
    df = read_file(filepath, comment=None, header=None)

    # データのクリーニング
    df = clean_data_frame(df)

    # csv形式で書き出し
    df.to_csv(outpath, header=False, index=False)


def clean_data_frame(df, drop_na=True, verbose=False):
    ndf = df.copy()
    nrow0, ncol0 = ndf.shape
    # Excelの浮動小数点計算精度が原因の変な値を置換
    ndf = ndf.applymap(clean_float)
    # 日付がdatetime型になっている要素をyyyymmddの文字列に変換
    ndf = ndf.applymap(datetime_to_yyyymmdd)
    # 半角文字を全角に変換
    ndf = ndf.applymap(normalize_chrs)
    # セル内改行、タブ、垂直タブ、改頁を削除
    ndf = ndf.replace("\r\n|\n|\r|\t|\x0b|\x0c", "", regex=True)
    # 空白行・列を削除
    if drop_na:
        ndf = ndf.dropna(how="all", axis=1).dropna(how="all", axis=0)
        nrow1, ncol1 = ndf.shape
        dropped = nrow0 - nrow1, ncol0 - ncol1

        if sum(dropped) > 0 and verbose:
            msg = "Dropped some empty row(s) and/or colmun(s): "
            msg += "({})".format(", ".join([str(i) for i in dropped]))
            print(msg)

    return ndf


def normalize_chrs(x):
    """
    Unicode文字の標準化
    半角カナ -> 全角カナ
    全角数字 -> 半角数字
    """
    if isinstance(x, str):
        return unicodedata.normalize("NFKC", x)
    else:
        return x


def clean_float(x):
    pat = re.compile(r"(\d*\.\d{14,})")
    m = pat.match(str(x))
    if m:
        "{:.3f}".format(float(m.group(0))).rstrip("0")
    else:
        return x


def datetime_to_yyyymmdd(x):
    pat_datetime = re.compile(r"(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})")
    m = pat_datetime.match(str(x))
    if m:
        return dt.strftime(dt.strptime(m.group(1), "%Y-%m-%d %H:%M:%S"), "%Y%m%d")
    else:
        return x
