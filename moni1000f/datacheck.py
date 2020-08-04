import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.stats as stats

from .base import Moni1000DataFrame, read_data, read_file

fd = Path(__file__).resolve().parents[0]
path_splist_tree_default = fd.joinpath("suppl_data", "tree_species_list.csv")
path_splist_seed_default = fd.joinpath("suppl_data", "seed_species_list.csv")
path_xy_default = fd.joinpath("suppl_data", "mesh_xy.json")
path_trap_default = fd.joinpath("suppl_data", "trap_list.json")


@dataclass
class ErrorDat:
    plot_id: str
    rec_id1: str
    rec_id2: str
    err_type: str


class CheckDataCommon(object):
    """
    Check errors in Moni1000 data.

    共通のチェック項目
    """

    df_splist = pd.DataFrame()
    xy_combn = []
    trap_list = []

    def __init__(self, df, path_splist="", path_xy="", path_trap="", **kwargs):
        self.df = df
        if not isinstance(df, Moni1000DataFrame):
            raise TypeError("'df' is not Moni1000DataFrame object")

        if df.data_type == "tree":
            pat_meas_col = "^gbh[0-9]{2}$"
            pat_except = "^(?<![nd])d(?![d])|^dd$|^NA$|^na$|^na<5|^vi|^vn|^cd|^nd"
            pat_rec_id = "tag_no"
        elif df.data_type == "litter":
            pat_meas_col = "^w_|^wdry_"
            pat_except = "^NA$|^na$|^nd|^-$"
            pat_rec_id = "s_date1"
        elif df.data_type == "seed":
            pat_meas_col = "^number|^wdry"
            pat_except = "^NA$|^na$|^nd|^-$"
            pat_rec_id = "s_date1"
        else:
            raise TypeError("The data is not in the format of Moni1000 data")

        self.df_meas = self.df.filter(regex=pat_meas_col).copy()
        self.col_meas = self.df_meas.columns.values
        self.meas_orig = self.df_meas.values
        self.rec_id = self.df[pat_rec_id].values
        self.pat_except = re.compile(pat_except)

        if path_splist:
            self.df_splist = read_file(path_splist)

        if path_xy:
            with open(path_xy) as f:
                d_xy = json.load(f)
            if df.plot_id in d_xy:
                self.xy_combn = list(product(*d_xy[df.plot_id].values()))

        if path_trap:
            with open(path_trap) as f:
                d_trap = json.load(f)
            self.trap_list = d_trap[df.plot_id]["trap_id"]

    def check_invalid_date(self):
        df_date = self.df.filter(regex="^s_date").copy()
        date_orig = df_date.values
        df_date = df_date.replace("^NA$|^na$|^nd", np.nan, regex=True)
        valid = np.vectorize(lambda x: isdate(x, if_nan=True))(df_date)
        msg = "{}に不正な入力値 ({})"
        errors = [
            ErrorDat(self.df.plot_id, self.rec_id[i], "",
                     msg.format(df_date.columns[j], date_orig[i, j]))
            for i, j in zip(*np.where(~valid))
        ]
        return errors

    def check_sp_not_in_list(self):
        """種リストにない"""
        errors = []
        if self.df_splist.empty:
            return errors
        splist_obs = np.unique(self.df.filter(regex="^spc$|^spc_japan$"))
        splist_all = self.df_splist.name_jp.values
        sp_not_in_list = [sp for sp in splist_obs if sp not in splist_all]
        msg = "変則的な種名もしくは標準和名だがリストにない種 ({})"
        if sp_not_in_list:
            for sp in sp_not_in_list:
                if self.df.data_type == "tree":
                    tag = [
                        str(i) for i in self.df[self.df["spc_japan"] == sp]["tag_no"]
                    ]
                    rec_id1 = "; ".join(tag)
                else:
                    rec_id1 = ""
                errors.append(ErrorDat(self.df.plot_id, rec_id1, "", msg.format(sp)))
        return errors

    def check_synonym(self):
        """同種が2つ以上の名前で入力されている"""
        errors = []
        if self.df_splist.empty:
            return errors
        splist_obs = np.unique(self.df.filter(regex="^spc$|^spc_japan$"))
        sp_in_list = self.df_splist[self.df_splist["name_jp"].isin(splist_obs)]
        dups = [sp for sp, n in sp_in_list["species"].value_counts().items() if n > 1]
        for sp in dups:
            synonyms = sp_in_list[sp_in_list["species"] == sp]["name_jp"].tolist()
            msg = "同種が2つの名前で入力 ({})".format("/".join(synonyms))
            errors.append(ErrorDat(self.df.plot_id, "", "", msg))
        return errors

    def check_local_name(self):
        """非標準和名"""
        errors = []
        if self.df_splist.empty:
            return errors
        splist_obs = np.unique(self.df.filter(regex="^spc$|^spc_japan$"))
        sp_in_list = self.df_splist[self.df_splist["name_jp"].isin(splist_obs)]
        for sp, spstd in zip(sp_in_list["name_jp"], sp_in_list["name_jp_std"]):
            if spstd is not np.nan:
                msg = "{}は非標準和名（{}の別名）".format(sp, spstd)
                if self.df.data_type == "tree":
                    tag = [i for i in self.df[self.df["spc_japan"] == sp]["tag_no"]]
                    rec_id1 = "; ".join(tag)
                else:
                    rec_id1 = ""
                errors.append(ErrorDat(self.df.plot_id, rec_id1, "", msg))
        return errors

    def check_blank_in_data_cols(self):
        """
        check blank (NaN) in measurements data columns.

        測定値データの空白
        """
        errors = []
        if self.df_meas.isnull().values.any():
            msg = "測定値データ列に空白セルあり"
            errors.extend([
                ErrorDat(
                    self.df.plot_id, self.rec_id[i], self.col_meas[j]
                    if self.df.data_type == "tree" else self.df.trap_id[i], msg)
                for i, j in zip(*np.where(self.df_meas.isnull()))
            ])
        return errors

    def check_invalid_values(self):
        """測定値の無効な入力"""
        valid = self.df_meas.applymap(lambda x: isvalid(x, self.pat_except))
        msg = "{}が無効な入力値 ({})"
        errors = [
            ErrorDat(
                self.df.plot_id, self.rec_id[i],
                self.col_meas[j] if self.df.data_type == "tree" else self.df.trap_id[i],
                msg.format(self.col_meas[j], self.meas_orig[i, j]))
            for i, j in zip(*np.where(~valid))
        ]
        return errors

    def mask_invalid_values(self):
        """
        mask invalid values in measurements.

        測定値の無効な入力値をNaNに置換
        """
        valid = self.df_meas.applymap(lambda x: isvalid(x, self.pat_except))
        self.df_meas = self.df_meas[valid]

    def check_positive(self):
        """Check if value is positive."""
        df_meas_c = self.df_meas.applymap(lambda x: isvalid(x, return_value=True))
        values = df_meas_c.fillna(0).values

        msg = "{}の測定値がマイナス ({})"
        errors = [
            ErrorDat(
                self.df.plot_id,
                self.rec_id[i],
                self.col_meas[j] if self.df.data_type == "tree" else self.df.trap_id[i],
                msg.format(self.col_meas[j], values[i, j]),
            ) for i, j in zip(*np.where(values < 0))
        ]
        return errors


class CheckDataTree(CheckDataCommon):
    """毎木データのチェック"""
    def __init__(self, df, **kwargs):
        super().__init__(df, **kwargs)

    def check_tag_dup(self):
        """タグ番号の重複"""
        msg = "タグ番号の重複"
        tag_counts = self.df["tag_no"].value_counts()
        errors = [
            ErrorDat(self.df.plot_id, i, "", msg) for i, n in tag_counts.items()
            if n > 1
        ]
        return errors

    def check_sp_mismatch(self):
        """同株で樹種が異なる"""
        indv_no = self.df["indv_no"]
        indv_no = indv_no.replace("|".join(["na", "NA"]), "na", regex=True)
        indv_no = indv_no.fillna("na")
        errors = []
        for i, n in indv_no.value_counts().items():
            if i == "na":
                s = self.df[self.df["indv_no"] == i]
                tag = "; ".join([str(j) for j in s["tag_no"]])
                msg = "indv_noが空白またはna"
                errors.append(ErrorDat(self.df.plot_id, tag, "indv_no", msg))
            elif n > 1:
                s = self.df[self.df["indv_no"] == i]
                if len(s["spc_japan"].unique()) > 1:
                    tag = "; ".join([str(j) for j in s["tag_no"]])
                    target = "/".join(s["spc_japan"].unique().tolist())
                    msg = "同株だが樹種が異なる"
                    errors.append(ErrorDat(self.df.plot_id, tag, target, msg))
        return errors

    def check_mesh_xy(self):
        "mesh_[xy]cordのエラー"
        errors = []
        if not self.xy_combn:
            return errors

        for i, xy in enumerate(self.df.filter(regex="^mesh_[xy]cord$").values):
            tag = self.rec_id[i]
            target = "mesh_xycord = {}".format(str(xy))
            try:
                if not tuple(xy.astype(int)) in self.xy_combn:
                    msg = "調査地に存在しないxy座標の組み合わせ"
                    errors.append(ErrorDat(self.df.plot_id, tag, target, msg))
            except ValueError:
                if any([j in ["nd", "na", "NA"] for j in xy]):
                    pass
                elif list(xy).count("") > 0:
                    msg = "mesh_xycordに空白セル"
                    errors.append(ErrorDat(self.df.plot_id, tag, target, msg))
                else:
                    msg = "mesh_xycordの入力値が非数値"
                    errors.append(ErrorDat(self.df.plot_id, tag, target, msg))
        return errors

    def check_stem_xy(self):
        "stem_[xy]cordのエラー"
        errors = []
        if not self.xy_combn:
            return errors

        for i, xy in enumerate(self.df.filter(regex="^stem_[xy]cord$").values):
            tag = self.rec_id[i]
            target = "stem_xycord = {}".format(str(xy))
            try:
                np.array(xy).astype(np.float64)
            except ValueError:
                if any([j in ["nd", "na", "NA"] for j in xy]):
                    pass
                elif list(xy).count("") > 0:
                    msg = "stem_xycordに空白セル"
                    errors.append(ErrorDat(self.df.plot_id, tag, target, msg))
                else:
                    msg = "stem_xycordの入力値が非数値"
                    errors.append(ErrorDat(self.df.plot_id, tag, target, msg))
        return errors

    def replace_dxx_in_gbh(self):
        """枯死個体のgbhが'dxx.xx'と入力されている場合は'd'に変換"""
        pat_dxx = re.compile(r"(?<![nd])d(?![d])\s?([0-9]+[.]?[0-9]*)")
        match_dxx = self.df_meas.applymap(lambda x: find_pattern(x, pat_dxx)).values
        for i, j in zip(*np.where(match_dxx)):
            if j > 0 and match_dxx[i, j - 1]:
                # 複数年に渡って"dxx.xx"と入力されている場合は、2つ目以降を'na'にする
                self.df_meas.iloc[i, j] = "na"
            else:
                self.df_meas.iloc[i, j] = "d"

    def check_missing(self):
        """前年まで生存していた個体がnaになっている"""
        pat_na = re.compile(r"^na$|^NA$")
        match_na = self.df_meas.applymap(
            lambda x: find_pattern(x, pattern=pat_na)).values
        alive = self.df_meas.applymap(
            lambda x: isalive(x, pattern_except=self.pat_except)).values

        msg = "前年まで生存。枯死？"
        errors = [
            ErrorDat(self.df.plot_id, self.rec_id[i], self.col_meas[j], msg)
            for i, j in zip(*np.where(match_na)) if j > 0 and alive[i, j - 1]
        ]
        return errors

    def check_values_after_d(self):
        """dの次の値がnaあるいはddになっていない"""
        pat_d = re.compile(r"^d$")
        match_d = self.df_meas.applymap(lambda x: find_pattern(x, pat_d)).values
        pat_dd = re.compile(r"^dd$|^na$|^NA$")
        match_dd = self.df_meas.applymap(lambda x: find_pattern(x, pat_dd)).values

        msg = "枯死の次の調査時のgbhが「na」もしくは「dd」になっていない"
        errors = [
            ErrorDat(self.df.plot_id, self.rec_id[i], self.col_meas[j], msg)
            for i, j in zip(*np.where(match_d))
            if j < (len(self.col_meas) - 1) and not match_dd[i, j + 1]
        ]
        return errors

    def check_anomaly(self):
        """成長量が基準より大きいあるいは小さい"""
        # NOTE: 前回の値にcd, vn, viが付く場合はスキップ
        values_cleaned = self.df_meas.applymap(
            lambda x: isvalid(x, return_value=True)).values
        pat_vc = re.compile("^vi|^vn|^cd")
        match_vc = self.df_meas.applymap(lambda x: find_pattern(x, pat_vc)).values

        errors = []
        for i, row in enumerate(values_cleaned):
            index_notnull = np.where(~np.isnan(row))[0]
            gbhdiff = np.diff(row[index_notnull])
            yrdiff = np.diff(
                [int(x.replace("gbh", "")) for x in self.col_meas[index_notnull]])

            excess = gbhdiff > yrdiff * 2.5 + 3.8
            minus = gbhdiff < -3.1
            index_excess = index_notnull[1:][excess]
            index_minus = index_notnull[1:][minus]

            msg = "成長量が基準値より大きい。測定ミス？"
            errors.extend([
                ErrorDat(self.df.plot_id, self.rec_id[i], self.col_meas[j], msg)
                for j in index_excess if not match_vc[i, j - 1]
            ])

            msg = "成長量が基準値より小さい。測定ミス？"
            errors.extend([
                ErrorDat(self.df.plot_id, self.rec_id[i], self.col_meas[j], msg)
                for j in index_minus if not match_vc[i, j - 1]
            ])
        return errors

    def check_values_recruits(self):
        # 新規加入個体（naの次のgbhが数値）のサイズが基準より大きい
        values_cleaned = self.df_meas.applymap(
            lambda x: isvalid(x, return_value=True)).values
        notnull = ~np.isnan(values_cleaned)
        pat_na = re.compile(r"^na$|^NA$")
        match_na = self.df_meas.applymap(
            lambda x: find_pattern(x, pattern=pat_na)).values
        msg = "新規加入個体だが、加入時のgbhが基準より大きいのため前回計測忘れの疑い"
        errors = []
        for i, j in zip(*np.where(match_na[:, :-1] & notnull[:, 1:])):
            yrdiff = np.diff(
                [int(x.replace("gbh", "")) for x in self.col_meas[[j, (j + 1)]]])[0]
            if values_cleaned[i, j + 1] >= (15 + yrdiff * 2.5 + 3.8):
                target = "{}={}; {}={}".format(self.col_meas[j], self.meas_orig[i, j],
                                               self.col_meas[j + 1],
                                               self.meas_orig[i, j + 1])
                errors.append(ErrorDat(self.df.plot_id, self.rec_id[i], target, msg))
        return errors

    def check_values_nd(self):
        """ndだが前後の測定値と比較して成長量の基準に収まっている"""
        pat_ndxx = re.compile(r"^nd\s?([0-9]+[.]?[0-9]*)")
        match_ndxx = self.df_meas.applymap(lambda x: find_pattern(x, pat_ndxx)).values
        values_cleaned = self.df_meas.applymap(
            lambda x: isvalid(x, re.compile("^nd"), return_value=True)).values

        errors = []
        for i, row in enumerate(values_cleaned):
            if any(match_ndxx[i]):
                index_notnull = np.where(~np.isnan(row))[0]
                index_match_ndxx = np.where(match_ndxx[i])[0]

                gbhdiff = np.diff(row[index_notnull])
                yrdiff = np.diff(
                    [int(x.replace("gbh", "")) for x in self.col_meas[index_notnull]])

                in_range = (gbhdiff <= yrdiff * 2.5 + 3.8) & (gbhdiff >= -3.1)

                index_notnull[1:][in_range]
                index_match_ndxx

                msg = "誤って「nd: 測定間違い」となっている可能性あり"
                for jj in np.where(match_ndxx[i][index_notnull][1:])[0]:
                    j = index_notnull[jj + 1]
                    # 最初か最後の調査時のndはスキップ
                    if (j < (len(self.col_meas) - 1)) and (jj < (len(in_range) - 1)):
                        if all(in_range[jj:(jj + 2)]):
                            errors.append(
                                ErrorDat(self.df.plot_id, self.rec_id[i],
                                         self.col_meas[j], msg))
        return errors

    def check_all(self, throughly=False):
        """すべての項目をチェック"""
        errors = []
        errors.extend(self.check_invalid_date())
        errors.extend(self.check_sp_not_in_list())
        errors.extend(self.check_synonym())
        errors.extend(self.check_tag_dup())
        errors.extend(self.check_sp_mismatch())
        errors.extend(self.check_mesh_xy())
        errors.extend(self.check_stem_xy())
        errors.extend(self.check_blank_in_data_cols())
        errors.extend(self.check_invalid_values())
        self.mask_invalid_values()
        self.replace_dxx_in_gbh()
        errors.extend(self.check_missing())
        errors.extend(self.check_values_after_d())
        errors.extend(self.check_anomaly())
        errors.extend(self.check_values_recruits())
        errors.extend(self.check_values_nd())
        if throughly:
            errors.extend(self.check_local_name())
        return errors


class CheckDataLitter(CheckDataCommon):
    """リターデータのチェック"""
    def __init__(self, df, **kwargs):
        super().__init__(df, **kwargs)
        self.period = (self.df.s_date1 + "-" + self.df.s_date2).values

    def check_trap_date_combinations(self):
        """同じ設置・回収日でトラップの重複・欠落がないか"""
        # 同じ時期でも数日に分けて回収した場合などもあり、必ずしもエラーではない
        errors = []
        for period_s, n_trap in zip(*np.unique(self.period, return_counts=True)):
            s_date1_s, s_date2_s = period_s.split("-")
            trap_s = self.df.trap_id[np.where(self.period == period_s)[0]]
            trap_dup = find_duplicates(trap_s)
            if trap_dup.size > 0:
                msg = "同じ設置・回収日の組み合わせでトラップの重複あり"
                msg += " ({})".format("; ".join(trap_dup))
                errors.append(ErrorDat(self.df.plot_id, s_date1_s, "", msg))

            if n_trap < len(self.trap_list):
                msg = "同じ設置・回収日の組み合わせでトラップの欠落あり"
                trap_luck = [x for x in self.trap_list if x not in trap_s]
                msg += " ({})".format(";".join(trap_luck))
                errors.append(ErrorDat(self.df.plot_id, s_date1_s, "", msg))
        return errors

    def check_installation_period1(self):
        """設置期間が長い/短い"""
        errors = []
        s_date1_s, s_date2_s = zip(*[p.split("-") for p in np.unique(self.period)])
        s_date1_s = np.array(s_date1_s)
        s_date2_s = np.array(s_date2_s)
        s_date1_s_dt = np.array(list(map(as_datetime, s_date1_s)))
        s_date2_s_dt = np.array(list(map(as_datetime, s_date2_s)))
        delta_days = np.vectorize(calc_delta_days)(s_date1_s_dt, s_date2_s_dt)

        long_d = delta_days > 45
        # 越冬設置は除外
        overwinter_site = [
            "UR-BC1", "AS-DB1", "AS-DB2", "TM-DB1", "OY-DB1", "KY-DB1", "OT-EC1",
            "OG-DB1"
        ]
        within_year = np.array(
            [i.year == j.year for i, j in zip(s_date1_s_dt, s_date2_s_dt)])
        msg = "設置期間が46日以上"
        if self.df.plot_id in overwinter_site:
            errors.extend([
                ErrorDat(self.df.plot_id, d1, "", msg)
                for d1 in s_date1_s[long_d & within_year]
            ])
        else:
            errors.extend(
                [ErrorDat(self.df.plot_id, d1, "", msg) for d1 in s_date1_s[long_d]])

        # 設置期間が短い
        short_d = delta_days < 11
        msg = "設置期間が10日以下"
        errors.extend(
            [ErrorDat(self.df.plot_id, d1, "", msg) for d1 in s_date1_s[short_d]])

        return errors

    def check_installation_period2(self):
        """設置期間がトラップによって異なる"""
        s_date1_s, s_date2_s = zip(*[p.split("-") for p in np.unique(self.period)])
        s_date1_s = np.array(s_date1_s)
        s_date2_s = np.array(s_date2_s)
        msg = "設置期間がトラップによって異なる"
        errors = [
            ErrorDat(self.df.plot_id, d1, "", msg) for d1 in np.unique(s_date1_s)
            if len(s_date2_s[s_date1_s == d1]) > 1
        ]
        return errors

    def check_installation_period3(self):
        """設置日と前回の回収日のずれ"""
        errors = []
        for trap in self.df.trap_id.unique():
            s_date1_s = self.df.s_date1[self.df.trap_id == trap].values
            s_date2_s = self.df.s_date2[self.df.trap_id == trap].values
            s_date1_s_dt = np.array(list(map(as_datetime, s_date1_s)))
            s_date2_s_dt = np.array(list(map(as_datetime, s_date2_s)))

            delta_days = np.vectorize(calc_delta_days)(s_date2_s_dt[:-1],
                                                       s_date1_s_dt[1:])

            interrupted = (delta_days != 0) & (delta_days < 45)
            within_year = np.array(
                [i.year == j.year for i, j in zip(s_date2_s_dt[:-1], s_date1_s_dt[1:])])

            msg = "前回の回収日から{}日間の中断期間"
            errors.extend([
                ErrorDat(self.df.plot_id, s_date1_s[i + 1], trap,
                         msg.format(delta_days[i]))
                for i in np.where(interrupted & within_year)[0]
            ])
        return errors

    def check_anomaly(self):
        """重量データの異常値の検出"""
        # 器官・回収日ごとにスミルノフ-グラブス検定により外れ値を検出
        # 数値以外の文字列はnanに置換
        # 0が多い月はそれ以外の値が外れ値になるので、0も除外
        # 絶乾重量（wdry）のみ
        df_wdry = self.df_meas.filter(regex="^wdry_").copy()
        df_wdry = df_wdry.replace("^0$", np.nan, regex=True)
        values_cleaned = df_wdry.applymap(
            lambda x: isvalid(x, "^NA$|^na$|^-$", return_value=True)).values
        with np.errstate(invalid="ignore"):
            values_cleaned[values_cleaned < 0] = np.nan

        msg = "{}は外れ値の可能性あり"
        errors = []
        for period_s in np.unique(self.period):
            d1 = period_s.split("-")[0]
            values_s = values_cleaned[self.period == period_s]
            trap_id_s = self.df.trap_id[self.period == period_s].values

            for j, vals in enumerate(np.transpose(values_s)):
                if np.sum(~np.isnan(vals)) < 5:
                    continue
                outlier = smirnov_grubbs(np.log(vals))
                errors.extend([
                    ErrorDat(self.df.plot_id, d1, trap_id_s[i],
                             msg.format(df_wdry.columns[j]))
                    for i in np.where(outlier)[0]
                ])
        return errors

    def check_all(self, throughly=False):
        """すべての項目をチェック"""
        errors = []
        errors.extend(self.check_invalid_date())
        # 日付に不正な入力値がある場合はここで終了
        if errors:
            print("日付に不正な入力値")
            return errors
        errors.extend(self.check_trap_date_combinations())
        errors.extend(self.check_installation_period1())
        errors.extend(self.check_installation_period2())
        errors.extend(self.check_installation_period3())
        errors.extend(self.check_blank_in_data_cols())
        errors.extend(self.check_invalid_values())
        self.mask_invalid_values()
        errors.extend(self.check_positive())
        errors.extend(self.check_anomaly())

        return errors


class CheckDataSeed(CheckDataCommon):
    """種子データのチェック"""
    def __init__(self, df, **kwargs):
        super().__init__(df, **kwargs)
        self.period = (self.df.s_date1 + "-" + self.df.s_date2).values

    def check_sp_not_in_list(self):
        """種名リストにないj"""
        # NOTE: 一時的にリスト外の種をカレントディレクトリに書き出すようにしている(2020-8-1)
        errors = []
        if self.df_splist.empty:
            return errors
        splist_all = self.df_splist.name_jp.values
        splist = self.df.spc.unique()
        sp_not_in_list = [i for i in splist if i not in splist_all]
        if sp_not_in_list:
            o_new = Path("seed_species_new.csv")
            if o_new.exists():
                with o_new.open("r", encoding="utf-8") as infile:
                    splist_new = [l.strip().split(",")[1] for l in infile.readlines()]
                outfile = o_new.open("a", encoding="utf-8")
            else:
                outfile = o_new.open("w", encoding="utf-8")
                outfile.write("plotid,spc_japan\n")
                splist_new = []

            for sp in sp_not_in_list:
                if sp not in splist_new + ["不明", "nd"]:
                    outfile.write(self.df.plot_id + "," + sp + "\n")
                msg = "{}はモニ1000種リストにない".format(sp)
                for i in self.df[self.df["spc"] == sp].itertuples():
                    errors.append(ErrorDat(self.df.plot_id, i.s_date1, i.trap_id, msg))

            outfile.close()
        return errors

    def check_trap(self):
        """トラップリストとの整合性チェック"""
        errors = []
        if not self.trap_list:
            return errors
        trap_uniq = self.df["trap_id"].unique()
        trap_not_in_list = [i for i in trap_uniq if i not in self.trap_list]
        for trap in trap_not_in_list:
            msg = "リストにないtrap_id ({})".format(trap)
            for i in self.df[self.df["trap_id"] == trap].itertuples():
                errors.append(ErrorDat(self.df.plot_id, i.s_date1, trap, msg))
        return errors

    def check_all(self, throughly=False):
        """すべての項目をチェック"""
        errors = []
        errors.extend(self.check_invalid_date())
        errors.extend(self.check_sp_not_in_list())
        errors.extend(self.check_synonym())
        errors.extend(self.check_local_name())
        errors.extend(self.check_blank_in_data_cols())
        errors.extend(self.check_trap())
        errors.extend(self.check_invalid_values())
        errors.extend(self.check_positive())

        return errors


def isvalid(s: str, pattern_except="", return_value=False):
    """Check if the value is a numeric or one of the exceptions."""
    if isinstance(pattern_except, str):
        pattern_except = re.compile(pattern_except)

    try:
        s = pattern_except.sub("", str(s))
        f = float(np.nan if s == "" else s)
        return f if return_value else True
    except ValueError:
        return np.nan if return_value else False


def find_pattern(s: str, pattern):
    """Find a pattern in the given string and return a Boolean value."""
    if isinstance(pattern, str):
        pattern = re.compile(pattern)

    if pattern.match(str(s)):
        return True
    else:
        return False


def isalive(s: str, gbh_threthold: float = 15, pattern_except=[]):
    """Check whether the GBH larger than the threthold."""
    if isvalid(s, pattern_except, return_value=True) >= gbh_threthold:
        return True
    else:
        return False


def isdate(s_date: str, if_nan=False):
    """Check whether the date string is yyyymmdd format or not."""
    try:
        datetime.strptime(s_date, "%Y%m%d")
        return True
    except ValueError:
        return False
    except TypeError:
        return if_nan


def as_datetime(s_date, format="%Y%m%d"):
    """Convert the string in yyyymmdd format to the datetime object."""
    if isdate(s_date, if_nan=False):
        return datetime.strptime(s_date, format)
    else:
        return np.datetime64("NaT")


def find_duplicates(array):
    """Find duplicates."""
    uniq, counts = np.unique(array, return_counts=True)
    return uniq[counts > 1]


def dt64_to_dt(dt64):
    """Convert the numpy.datetime64 object to the datetime object."""
    try:
        return datetime.strptime(dt64.astype("datetime64[D]").astype("str"), "%Y-%m-%d")
    except ValueError:
        return np.nan


def return_growth_year(dt):
    """
    Return the growth year.

    調査日から成長年を返す（8月以前に調査した場合は前年を成長年とする）
    """
    if isinstance(dt, np.datetime64):
        dt = dt64_to_dt(dt)
    try:
        if dt.month < 8:
            return dt.year - 1
        else:
            return dt.year
    except AttributeError:
        return -1


def calc_delta_days(d1, d2):
    """Calculate the day difference between datetime objects."""
    if isinstance(d1, datetime) and isinstance(d2, datetime):
        return (d2 - d1).days
    else:
        raise TypeError("d1 and d2 must be datetime.datetime objects")


def smirnov_grubbs(x, alpha=0.01):
    """Outlier detection by Smirnov-Grubbs test."""
    x = np.array(x)
    xs = x[~np.isnan(x)]
    i_out = np.array([], dtype=np.int64)

    while True:
        n = len(xs)
        if n < 5:
            break
        t = stats.t.isf(q=((alpha / n) / 2), df=(n - 2))
        tau = (n - 1) * t / np.sqrt(n * (n - 2) + n * t**2)
        mu, sd = xs.mean(), xs.std(ddof=1)
        if sd == 0:
            break
        far = xs.max() if np.abs(xs.max() - mu) > np.abs(xs.min() - mu) else xs.min()
        tau_far = np.abs((far - mu) / sd)
        if tau_far < tau:
            break
        i_out = np.append(i_out, np.where(x == far)[0])
        xs = np.delete(xs, np.where(xs == far)[0])

    return [True if i in i_out else False for i in range(len(x))]


def get_except_list(path_exceptlist: str, plot_id: str = ""):
    """例外リストの読み込み."""
    df_except = read_file(path_exceptlist)
    df_except = df_except.fillna("")
    df_except = df_except.drop("response", axis=1)
    if plot_id:
        df_except = df_except[df_except["plot_id"] == plot_id]
    return [ErrorDat(*e) for e in df_except.values]


def save_errors_to_xlsx(errors, outfile, colnames, sortcol=""):
    """Save the error list in a XLSX file."""
    df_err = pd.DataFrame([asdict(x) for x in errors])
    df_err.columns = colnames
    df_err["サイトでの対応"] = ""
    if sortcol:
        df_err = df_err.sort_values(sortcol)

    sheet_name = "確認事項{}".format(datetime.now().strftime("%y%m%d"))
    writer = pd.ExcelWriter(outfile, engine="xlsxwriter")
    df_err.to_excel(writer, index=False, sheet_name=sheet_name)
    workbook = writer.book
    worksheet = writer.sheets[sheet_name]
    header_fmt = workbook.add_format({"bold": True, "border": 0, "fg_color": "#7e7e7e"})
    [
        worksheet.write(0, col_num, col_value, header_fmt)
        for col_num, col_value in enumerate(df_err.columns.values)
    ]
    writer.save()


def check_data(df: Moni1000DataFrame,
               path_splist: str = "",
               path_xy: str = "",
               path_trap: str = "",
               path_except: str = "",
               throughly=False):
    """
    Check errors in Moni1000 data.

    Parameters
    ----------
    df: Moni1000DataFrame
    path_splist: str
    path_xy: str
    path_trap: str
    path_exceptlist: str
    """
    global path_splist_seed_default
    global path_splist_tree_default
    global path_xy_default
    global path_trap_default

    if df.data_type == 'tree':
        if not path_splist:
            path_splist = path_splist_tree_default
        if not path_xy:
            path_xy = path_xy_default
        d = CheckDataTree(df, path_splist=path_splist, path_xy=path_xy)
    elif df.data_type == 'litter':
        if not path_trap:
            path_trap = path_trap_default
        d = CheckDataLitter(df, path_trap=path_trap)
    elif df.data_type == 'seed':
        if not path_splist:
            path_splist = path_splist_seed_default
        if not path_trap:
            path_trap = path_trap_default
        d = CheckDataSeed(df, path_splist=path_splist, path_trap=path_trap)
    else:
        raise TypeError("Data 'df' is not Moni1000DataFrame object")

    errors = d.check_all(throughly=throughly)

    if path_except and errors:
        # 例外リストにあるエラー項目を除外
        except_list = get_except_list(path_except, df.plot_id)
        errors = [e for e in errors if e not in except_list]

    return errors


def check_data_file(filepath: str, outdir: str = "", return_msg=False, **kwargs):
    """
    データファルのエラーをチェックし、結果をxlsxファイルで書き出す
    """
    filepath = Path(filepath)

    if outdir:
        outdir = Path(outdir)
    else:
        outdir = filepath.parent

    if not outdir.exists:
        outdir.mkdir(parents=True, exist_ok=True)

    df = read_data(filepath)
    if df.data_type == "other":
        msg = "File is not the Moni1000 data"
        if return_msg:
            return msg
        else:
            print(msg)
            return

    errors = check_data(df, **kwargs)

    if errors:
        if df.data_type == "tree":
            colnames = ["plotid", "tag_no", "エラー対象", "エラー内容"]
            sortcol = ["tag_no"]
        else:
            colnames = ["plotid", "s_date1", "trap_id", "エラー内容"]
            sortcol = ["s_date1", "trap_id"]

        outfile = outdir.joinpath("確認事項{}.xlsx".format(filepath.stem))
        save_errors_to_xlsx(errors, outfile, colnames, sortcol)
        msg = "Output file {} was created.".format(outfile.name)
    else:
        msg = "No error detected."

    if return_msg:
        return msg
    else:
        print(msg)
        return 0
