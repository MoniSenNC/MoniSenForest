import copy
import json
from pathlib import Path
from typing import Any

import numpy as np

from MoniSenForest.base import MonitoringData
from MoniSenForest.datacheck import find_pattern, isvalid, retrive_year
from MoniSenForest.logger import get_logger

logger = get_logger(__name__)

fd = Path(__file__).resolve().parents[0]
path_spdict = fd.joinpath("suppl_data", "species_dict.json")
with open(path_spdict, "rb") as f:
    dict_sp = json.load(f)


def fill_after(x: np.ndarray, val: Any = 1, fill: Any = 2) -> np.ndarray:
    """
    Fill the elements after a specific value with a single value.

    Parameters
    ----------
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
        x[(i.min() + 1) :] = fill
    return x


def add_extra_columns_tree(d: MonitoringData) -> MonitoringData:
    """
    Add error/death/recruitment columns to a tree gbh data.

    毎木データに、エラー、死亡、加入の状態を表す列を追加。
    公開データに含まれるCSV2（*.transf.csv）。

    Parameters
    ----------
    d : MonitoringData
        MonitoringData object of tree gbh data

    """
    d = copy.deepcopy(d)
    pat_gbh_col = "^gbh([0-9]{2})$"
    gbh_data = d.select(regex=pat_gbh_col, add_header=True)
    values = gbh_data[1:]
    colnames = gbh_data[0]
    yrs = np.array(list(map(retrive_year, colnames)))
    yrs_diff = np.diff(yrs)
    values_c = np.vectorize(lambda x: isvalid(x, "^nd|^cd|^vi|^vn", return_value=True))(
        values.copy()
    )

    # Error
    error1 = np.where(np.vectorize(lambda x: find_pattern(x, "^nd"))(values), 1, 0)
    error2 = np.where(
        np.vectorize(lambda x: find_pattern(x, "^cd|^vi|^vn"))(values), 2, 0
    )
    error = (error1 + error2).astype(np.int64)

    # Dead
    pat_dxx = r"(?<![nd])d(?![d])\s?([0-9]+[.]?[0-9]*)"
    match_dxx = np.vectorize(lambda x: find_pattern(x, pat_dxx))(values)
    for i, j in zip(*np.where(match_dxx)):
        if j > 0 and match_dxx[i, j - 1]:
            values[i, j] = "na"
        else:
            values[i, j] = "d"

    dead1 = np.where(
        np.vectorize(lambda x: find_pattern(x, "^(?<![nd])d(?![d])"))(values), 1, 0
    )
    dead2 = np.where(np.vectorize(lambda x: find_pattern(x, "^dd"))(values), 2, 0)
    dead = (dead1 + dead2).astype(np.int64)
    dead = np.apply_along_axis(lambda x: fill_after(x, 1, 2), 1, dead)

    # Recruit
    below_cutoff = np.vectorize(lambda x: np.less(x, 15.7, where=~np.isnan(x)))(
        values_c
    )
    recr = np.zeros(values_c.shape)

    # for first census
    not_recr_init = below_cutoff[:, 0] | np.isnan(values_c[:, 0]) | (dead[:, 0] == 1)
    recr[:, 0][not_recr_init & (error[:, 0] == 0)] = -1

    change_state = np.apply_along_axis(np.diff, 1, np.isnan(values_c) | below_cutoff)

    for i, j in zip(*np.where(change_state)):
        if np.isnan(values_c[i, j + 1]):
            continue
        elif values_c[i, j] > values_c[i, j + 1]:
            continue
        elif len(np.where(recr[i, : (j + 1)] == 1)[0]) == 0:
            if (error[i, j] == 0) & (error[i, j + 1] == 0):
                if values_c[i, j + 1] < (15.7 + 3.8 + yrs_diff[j] * 2.5):
                    recr[i, j + 1] = 1
                    recr[i, : (j + 1)] = -1
                elif not np.isnan(values_c[i, j]):
                    recr[i, j + 1] = 1
                    recr[i, : (j + 1)] = -1
                elif len(np.where(recr[i, : (j + 1)] == -1)[0]) > 0:
                    recr[i, :j] = -1
            elif error[i, j] == 1:
                if len(np.where(recr[i, : (j + 1)] == -1)[0]) > 0:
                    recr[i, : np.where(error[i, : (j + 1)] == 1)[0][0]] = -1

    recr = recr.astype(np.int64)

    # 元の計測値を全て、nd等の記号を取り除いた数値のみのデータに置換
    # NOTE: np.nanが文字列の'nan'になるので注意
    for j, c in enumerate(colnames):
        d.values[:, d.columns.tolist().index(c)] = values_c[:, j]

    # Add error, dead (dl), recruit (rec) columns to data
    error_colnames = [i.replace("gbh", "error") for i in colnames]
    dead_colnames = [i.replace("gbh", "dl") for i in colnames]
    recr_colnames = [i.replace("gbh", "rec") for i in colnames]
    error = np.vstack((error_colnames, error))
    dead = np.vstack((dead_colnames, dead))
    recr = np.vstack((recr_colnames, recr))

    d.data = np.hstack((d.data, error, dead, recr))
    return d


def add_taxon_info(
    d: MonitoringData, scientific_name: bool = True, classification: bool = False
) -> MonitoringData:
    """
    Add taxonomic information to tree-gbh/seed data.

    毎木/種子データに、種和名に基づいて分類学的情報を付加。

    Parameters
    ----------
    d : MonitoringData
        MonitoringData object of tree-gbh/seed data
    scientific_name : bool, default True
        If add scientific name
    classfication : bool, default True
        If add classification
    """
    if d.data_type not in ["tree", "seed"]:
        logger.warning("Input data is not tree data or seed data")
        return d

    global dict_sp

    class_cols = ["genus", "family", "order", "family_jp", "order_jp"]
    if scientific_name and classification:
        cols = ["species"] + class_cols
    elif scientific_name:
        cols = ["species"]
    elif classification:
        cols = class_cols
    else:
        logger.warning("No columns added.")
        return d

    add_cols = []
    not_found = []
    for i in d.select(regex="^spc_japan$|^spc$"):
        if i in dict_sp:
            add_cols.append([dict_sp[i][j] for j in cols])
        else:
            add_cols.append([""] * len(cols))
            if i not in not_found:
                not_found.append(i)

    if not_found:
        for i in not_found:
            msg = "{} not found in the species dictionary".format(i)
            logger.warning(msg)

    d.data = np.hstack((d.data, np.vstack((cols, add_cols))))
    return d
