import re
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from .datacheck import find_pattern, isvalid
from .base import clean_data_frame, read_file


def fill_after(x, val=1, fill=2):
    x = x.copy()
    i = np.where(x == val)[0]
    if len(i) > 0:
        x[(i.min() + 1) :] = fill
    return x


def retrive_year(x, regex_pattern=r"([0-9]+)"):
    if regex_pattern:
        x = re.sub(regex_pattern, r"\1", x)
    if len(x) == 2:
        return int(datetime.strptime(x, "%y").strftime("%Y"))
    elif len(x) == 4:
        return int(x)
    else:
        msg = "Could not retrive the year from the input string {}".format(x)
        raise RuntimeError(msg)


def add_recl_dead_error_columns(df):
    pat_gbh_col = "^gbh([0-9]{2})$"
    df_gbh = df.filter(regex=pat_gbh_col).copy()
    gbhyr = df_gbh.columns.values
    yrs = np.array(list((map(lambda x: retrive_year(x, pat_gbh_col), gbhyr))))
    yrs_diff = np.diff(yrs)
    df_gbh_clean = df_gbh.applymap(
        lambda x: isvalid(x, "^nd|^cd|^vi|^vn", return_value=True)
    )

    # error
    error1 = np.where(df_gbh.applymap(lambda x: find_pattern(x, "^nd")), 1, 0)
    error2 = np.where(df_gbh.applymap(lambda x: find_pattern(x, "^cd|^vi|^vn")), 2, 0)
    error = error1 + error2
    df_error = pd.DataFrame(error).astype("int64").astype(str)
    df_error.columns = df_gbh.columns.str.replace("gbh", "error")

    # dead
    pat_dxx = re.compile(r"(?<![nd])d(?![d])\s?([0-9]+[.]?[0-9]*)")
    match_dxx = df_gbh.applymap(lambda x: find_pattern(x, pat_dxx)).values
    for i, j in zip(*np.where(match_dxx)):
        if j > 0 and match_dxx[i, j - 1]:
            df_gbh.iloc[i, j] = "na"
        else:
            df_gbh.iloc[i, j] = "d"

    dead1 = np.where(
        df_gbh.applymap(lambda x: find_pattern(x, "^(?<![nd])d(?![d])")), 1, 0
    )
    dead2 = np.where(df_gbh.applymap(lambda x: find_pattern(x, "^dd")), 2, 0)
    dead = dead1 + dead2
    dead = np.apply_along_axis(lambda x: fill_after(x, 1, 2), 1, dead)
    df_dead = pd.DataFrame(dead).astype("int64").astype(str)
    df_dead.columns = df_gbh.columns.str.replace("gbh", "dl")

    # recruit
    values = df_gbh_clean.values
    below_cutoff = np.vectorize(lambda x: np.less(x, 15.7, where=~np.isnan(x)))(values)
    recl = np.zeros(values.shape)

    # For first census
    not_recl_at_first = below_cutoff[:, 0] | np.isnan(values[:, 0]) | (dead[:, 0] == 1)
    recl[:, 0][not_recl_at_first & (error[:, 0] == 0)] = -1

    change_state = np.apply_along_axis(np.diff, 1, np.isnan(values) | below_cutoff)

    for i, j in zip(*np.where(change_state)):
        if np.isnan(values[i, j + 1]):
            continue
        elif values[i, j] > values[i, j + 1]:
            continue
        elif len(np.where(recl[i, : (j + 1)] == 1)[0]) == 0:
            if (error[i, j] == 0) & (error[i, j + 1] == 0):
                if values[i, j + 1] < (15.7 + 3.8 + yrs_diff[j] * 2.5):
                    recl[i, j + 1] = 1
                    recl[i, : (j + 1)] = -1
                elif not np.isnan(values[i, j]):
                    recl[i, j + 1] = 1
                    recl[i, : (j + 1)] = -1
                elif len(np.where(recl[i, : (j + 1)] == -1)[0]) > 0:
                    recl[i, :j] = -1
            elif error[i, j] == 1:
                if len(np.where(recl[i, : (j + 1)] == -1)[0]) > 0:
                    recl[i, : np.where(error[i, : (j + 1)] == 1)[0][0]] = -1

    df_recl = pd.DataFrame(recl).astype("int64").astype(str)
    df_recl.columns = df_gbh.columns.str.replace("gbh", "rec")

    for c in df_gbh_clean.columns:
        df[c] = df_gbh_clean[c]
    df = df.join(df_dead)
    df = df.join(df_recl)
    df = df.join(df_error)

    return df


def tree_data_transform(filepath, outdir=None):
    """
    毎木調査データ（モニ1000形式）に新規加入、死亡、エラー列を加え、CSVで保存

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
    outpath = outdir.joinpath(basename + ".transf.csv")

    df0 = read_file(filepath, comment=None, header=None)
    df0 = clean_data_frame(df0, drop_na=False)
    comment_row = df0.iloc[:, 0].fillna("").str.contains("^#")

    # データに新規加入、死亡、エラー列を加える
    data = df0[~comment_row]
    col_names = data.iloc[0].values
    data = data.iloc[1:, :]
    data.columns = col_names
    data = data.reset_index(drop=True)
    data = add_recl_dead_error_columns(data)

    # メタデータ
    meta_data = df0[comment_row]
    n_col0 = meta_data.shape[1]
    n_col1 = data.shape[1] - meta_data.shape[1]
    spacer = np.full((meta_data.shape[0], n_col1), fill_value=np.nan)
    spacer = pd.DataFrame(spacer, columns=range(n_col0, n_col0 + n_col1))
    meta_data = meta_data.join(spacer)

    # データをCSVに書き出し
    meta_data.to_csv(outpath, header=False, index=False)
    data.to_csv(outpath, mode="a", index=False)
