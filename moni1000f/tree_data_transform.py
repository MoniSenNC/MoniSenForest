import csv
import re
from pathlib import Path
from typing import Any, Optional

import numpy as np

from moni1000f.base import MonitoringData, clean_data, read_file, split_comments
from moni1000f.datacheck import find_pattern, isvalid, retrive_year


def fill_after(x: np.ndarray, val: Any = 1, fill: Any = 2) -> np.ndarray:
    """
    Fill the elements after a specific value with a single value.

    Paramters
    ---------
    x : numpy ndarray
        One dimentional array
    val : any, default 1
        Value of the break point
    fill : any, default 2
        Value to use fill elements after the break point
    """
    x = np.array(x).copy()
    i = np.where(x == val)[0]
    if len(i) > 0:
        x[(i.min() + 1):] = fill
    return x


def add_state_columns(data: np.ndarray,
                      comments: Optional[np.ndarray] = None) -> np.ndarray:
    '''
    Add columns for error, death, recluitment status.

    毎木データに、エラー、死亡、加入の状態を表す列を追加。

    Parameters
    ----------
    data : numpy ndarray
        Two dimentional array including a header row
    comments : numpy ndarray, optional
        Array of comment lines. Number of columns should be same as data
    '''
    d = MonitoringData(data)
    pat_gbh_col = "^gbh([0-9]{2})$"
    gbh_data = d.select_cols(regex=pat_gbh_col, add_header=True)
    values = gbh_data[1:]
    colnames = gbh_data[0]
    yrs = np.array(list(map(retrive_year, colnames)))
    yrs_diff = np.diff(yrs)
    values_c = np.vectorize(lambda x: isvalid(x, "^nd|^cd|^vi|^vn", return_value=True))(
        values.copy())

    # Error
    error1 = np.where(np.vectorize(lambda x: find_pattern(x, "^nd"))(values), 1, 0)
    error2 = np.where(
        np.vectorize(lambda x: find_pattern(x, "^cd|^vi|^vn"))(values), 2, 0)
    error = (error1 + error2).astype(np.int64)

    # Dead
    pat_dxx = re.compile(r"(?<![nd])d(?![d])\s?([0-9]+[.]?[0-9]*)")
    match_dxx = np.vectorize(lambda x: find_pattern(x, pat_dxx))(values)
    for i, j in zip(*np.where(match_dxx)):
        if j > 0 and match_dxx[i, j - 1]:
            values[i, j] = "na"
        else:
            values[i, j] = "d"

    dead1 = np.where(
        np.vectorize(lambda x: find_pattern(x, "^(?<![nd])d(?![d])"))(values), 1, 0)
    dead2 = np.where(np.vectorize(lambda x: find_pattern(x, "^dd"))(values), 2, 0)
    dead = (dead1 + dead2).astype(np.int64)
    dead = np.apply_along_axis(lambda x: fill_after(x, 1, 2), 1, dead)

    # Recruit
    below_cutoff = np.vectorize(lambda x: np.less(x, 15.7, where=~np.isnan(x)))(
        values_c)
    recl = np.zeros(values_c.shape)

    # for first census
    not_recl_init = below_cutoff[:, 0] | np.isnan(values_c[:, 0]) | (dead[:, 0] == 1)
    recl[:, 0][not_recl_init & (error[:, 0] == 0)] = -1

    change_state = np.apply_along_axis(np.diff, 1, np.isnan(values_c) | below_cutoff)

    for i, j in zip(*np.where(change_state)):
        if np.isnan(values_c[i, j + 1]):
            continue
        elif values_c[i, j] > values_c[i, j + 1]:
            continue
        elif len(np.where(recl[i, :(j + 1)] == 1)[0]) == 0:
            if (error[i, j] == 0) & (error[i, j + 1] == 0):
                if values_c[i, j + 1] < (15.7 + 3.8 + yrs_diff[j] * 2.5):
                    recl[i, j + 1] = 1
                    recl[i, :(j + 1)] = -1
                elif not np.isnan(values_c[i, j]):
                    recl[i, j + 1] = 1
                    recl[i, :(j + 1)] = -1
                elif len(np.where(recl[i, :(j + 1)] == -1)[0]) > 0:
                    recl[i, :j] = -1
            elif error[i, j] == 1:
                if len(np.where(recl[i, :(j + 1)] == -1)[0]) > 0:
                    recl[i, :np.where(error[i, :(j + 1)] == 1)[0][0]] = -1

    recl = recl.astype(np.int64)

    error_colnames = [i.replace("gbh", "error") for i in colnames]
    dead_colnames = [i.replace("gbh", "dl") for i in colnames]
    recl_colnames = [i.replace("gbh", "rec") for i in colnames]
    error = np.vstack((error_colnames, error))
    dead = np.vstack((dead_colnames, dead))
    recl = np.vstack((recl_colnames, recl))

    for j, c in enumerate(colnames):
        d.values[:, d.columns.tolist().index(c)] = values_c[:, j]

    data_new = np.hstack((d.data, error, dead, recl))

    if isinstance(comments, np.ndarray):
        spacer = np.full((comments.shape[0], data_new.shape[1] - comments.shape[1]), "")
        comments_new = np.hstack((comments, spacer))
        data_new = np.vstack((comments_new, data_new))

    return data_new


def tree_data_transform(filepath: str,
                        outdir: Optional[str] = None,
                        cleaning: bool = True):
    """
    Add columns for error, death, recluitment status to a tree data, and write to
    a csv file.

    毎木調査データ（モニ1000形式）に新規加入、死亡、エラー列を加え、CSVで保存。

    Parameters
    ----------
    filepath : str
        Path to a tree data file
    outdir : str, default None
        Output directory
    cleaning: bool, default True
        If clean up the data
    """
    filepath = Path(filepath)
    if outdir:
        outdir = Path(outdir)
        outdir.mkdir(parents=True, exist_ok=True)
    else:
        outdir = filepath.parent

    basename = filepath.stem
    outpath = outdir.joinpath(basename + ".transf.csv")

    data = read_file(filepath)
    data, comments = split_comments(data)
    data_new = add_state_columns(data, comments)

    if cleaning:
        data = clean_data(data_new)
    with open(outpath, "w") as f:
        writer = csv.writer(f, delimiter=",", quotechar='"', quoting=csv.QUOTE_MINIMAL)
        for row in data_new:
            writer.writerow(row)
