import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.stats as stats

from moni1000f.utils import read_file


@dataclass
class err_dat_t:
    plotid: str
    tag_no: str
    target: str
    reason: str


@dataclass
class err_dat_l:
    plotid: str
    s_date1: str
    trap_id: str
    reason: str


class Moni1000Data(object):
    fd = Path(__file__).resolve().parents[0]

    def __init__(self, df, plotid, data_type):
        self.df = df
        self.__plotid = plotid
        self.__data_type = data_type

    @property
    def plotid(self):
        return self.__plotid

    @property
    def data_type(self):
        return self.__data_type

    @classmethod
    def from_file(cls, filepath, *args, **kwargs):
        filepath = Path(filepath)
        df = read_file(filepath, *args, **kwargs)
        data_type = guess_data_type(df)

        forest_type = ["AT", "EC", "BC", "EB", "DB"]
        ppat = re.compile(
            "|".join(["[A-Z]{{2}}-{}[0-9]".format(i) for i in forest_type])
        )
        m = ppat.search(filepath.name)
        if m:
            plotid = m.group()
        else:
            plotid = None

        return cls(df, plotid, data_type)

    def get_except_list(self):
        """例外リストの読み込み"""
        path_exceptlist = self.fd.joinpath(
            "except_list", "{}_except_list.csv".format(self.data_type)
        )
        if not path_exceptlist.exists():
            return
        df_except = read_file(path_exceptlist)
        df_except = df_except.fillna("")
        df_except = df_except[df_except["plotid"] == self.plotid]
        except_list = []
        for e in df_except.to_dict("records"):
            e.pop("response", None)
            if self.data_type == "tree":
                except_list.append(err_dat_t(**e))
            else:
                except_list.append(err_dat_l(**e))
        return except_list

    def _check_data_tree(self, thoroughly=False):
        """毎木データのチェック"""
        errors = []

        # 種名に関するエラー
        # 種名リストにない
        path_splist = self.fd.joinpath("suppl_data", "tree_species_list.csv")
        df_splist = pd.read_csv(path_splist, comment="#", dtype=str)
        splist_all = df_splist.name_jp.values
        splist = self.df.spc_japan.unique()
        sp_not_in_list = [i for i in splist if i not in splist_all]
        msg = "変則的な種名もしくは標準和名だがモニ1000リストにない種"
        if sp_not_in_list:
            for sp in sp_not_in_list:
                tag = "; ".join(
                    [str(i) for i in self.df[self.df["spc_japan"] == sp]["tag_no"]]
                )
                errors.append(err_dat_t(self.plotid, tag, sp, msg))

        # 同種が２つ以上の名前で入力されている
        sp_in_list = df_splist[df_splist["name_jp"].isin(splist)]
        dups = [sp for sp, n in sp_in_list["species"].value_counts().items() if n > 1]
        msg = "同種が2つの名前で入力"
        for sp in dups:
            synonyms = sp_in_list[sp_in_list["species"] == sp]["name_jp"].tolist()
            errors.append(err_dat_t(self.plotid, "", "/".join(synonyms), msg))

        # 非標準和名
        # NOTE: thoroughly=Trueの場合のみチェック
        if thoroughly:
            for sp, spstd in zip(sp_in_list["name_jp"], sp_in_list["name_jp_std"]):
                if spstd is not np.nan:
                    msg = "非標準和名（{}の別名）".format(spstd)
                    tag = [i for i in self.df[self.df["spc_japan"] == sp]["tag_no"]]
                    errors.append(err_dat_t(self.plotid, "; ".join(tag), sp, msg))

        # タグ重複
        msg = "タグ番号の重複"
        tag_counts = self.df["tag_no"].value_counts()
        errors.extend(
            [err_dat_t(self.plotid, i, "", msg) for i, n in tag_counts.items() if n > 1]
        )

        # 同種で樹種が異なる
        indv_no = self.df["indv_no"]
        indv_no = indv_no.replace("|".join(["na", "NA"]), "na", regex=True)
        indv_no = indv_no.fillna("na")
        for i, n in indv_no.value_counts().items():
            if i == "na":
                s = self.df[self.df["indv_no"] == i]
                tag = "; ".join([str(j) for j in s["tag_no"]])
                msg = "indv_noが空白またはna"
                errors.append(err_dat_t(self.plotid, tag, "indv_no", msg))
            elif n > 1:
                s = self.df[self.df["indv_no"] == i]
                if len(s["spc_japan"].unique()) > 1:
                    tag = "; ".join([str(j) for j in s["tag_no"]])
                    target = "/".join(s["spc_japan"].unique().tolist())
                    msg = "同株だが樹種が異なる"
                    errors.append(err_dat_t(self.plotid, tag, target, msg))

        # xy座標のエラー
        path_xylist = self.fd.joinpath("suppl_data", "tree_mesh_xy_list.csv")
        df_xy = read_file(path_xylist)
        df_xy_s = df_xy[df_xy["plotid"] == self.plotid]
        mesh_xylist = list(zip(df_xy_s.mesh_xcord, df_xy_s.mesh_ycord))
        cols = ["tag_no", "mesh_xcord", "mesh_ycord", "stem_xcord", "stem_ycord"]
        for i in self.df[cols].fillna("").astype(str).values:
            tag = i[0]
            mesh_xy = (i[1], i[2])
            target = "mesh_xycord = {}".format(str(mesh_xy))
            if mesh_xy not in mesh_xylist:
                if any([j in ["nd", "na", "NA"] for j in mesh_xy]):
                    pass
                elif mesh_xy.count("") > 0:
                    msg = "mesh_xycordに空白セル"
                    errors.append(err_dat_t(self.plotid, tag, target, msg))
                else:
                    msg = "調査地に存在しないxy座標の組み合わせ"
                    errors.append(err_dat_t(self.plotid, tag, target, msg))

            stem_xy = (i[3], i[4])
            target = "stem_xycord = {}".format(str(stem_xy))
            if any([j in ["nd", "na", "NA"] for j in stem_xy]):
                pass
            elif stem_xy.count("") > 0:
                msg = "stem_xycordに空白セル"
                errors.append(err_dat_t(self.plotid, tag, target, msg))
            else:
                try:
                    np.array(stem_xy).astype(np.float64)
                except ValueError:
                    msg = "stem_xycordの入力値が非数値"
                    errors.append(err_dat_t(self.plotid, tag, target, msg))

        # GBH測定値に関するエラー
        df_gbh = self.df.filter(regex="^gbh[0-9]{2}$").copy()

        # gbhデータに含まれる記号
        # d: "枯死", dd: "前年に枯死", na: "測定対象外", nd: "欠損またはエラー",
        # vi: "ツル込み", vn: "ツル抜き", cd: "測定位置の変更"
        # NOTE: "(?<![nd])d(?![d])": "d"一文字のみにマッチ（"nd", "dd"にはマッチしない）
        s_except = "^(?<![nd])d(?![d])|^dd$|^NA$|^na$|^na<5|^vi|^vn|^cd|^nd"
        pat_except = re.compile(s_except)

        gbhyr = df_gbh.columns.values
        tag_no = self.df["tag_no"].values
        values = df_gbh.values

        # 空白セルあり
        if df_gbh.isnull().values.any():
            msg = "gbhデータに空白セルあり"
            errors.extend(
                [
                    err_dat_t(self.plotid, tag_no[i], gbhyr[j], msg)
                    for i, j in zip(*np.where(df_gbh.isnull()))
                ]
            )

        # 無効な入力値
        valid = df_gbh.applymap(lambda x: isvalid(x, pat_except))
        msg = "無効な入力値"
        errors.extend(
            [
                err_dat_t(
                    self.plotid, tag_no[i], "{}={}".format(gbhyr[j], values[i, j]), msg
                )
                for i, j in zip(*np.where(~valid))
            ]
        )

        # 無効な入力値はNaNに置換
        df_gbh = df_gbh[valid]

        # 枯死個体のgbhが計測されていて、"dxx.xx"と入力されている場合は"d"に変換
        # ただし、複数年に渡って"dxx.xx"と入力されている場合は、最初を"d"とし、
        # それ以降を"na"にする
        pat_dxx = re.compile(r"(?<![nd])d(?![d])\s?([0-9]+[.]?[0-9]*)")
        match_dxx = df_gbh.applymap(lambda x: find_pattern(x, pat_dxx)).values
        for i, j in zip(*np.where(match_dxx)):
            if j > 0 and match_dxx[i, j - 1]:
                df_gbh.iloc[i, j] = "na"
            else:
                df_gbh.iloc[i, j] = "d"

        # 前年まで生存していた個体がnaになっている
        pat_na = re.compile(r"^na$|^NA$")
        match_na = df_gbh.applymap(lambda x: find_pattern(x, pattern=pat_na)).values
        alive = df_gbh.applymap(lambda x: isalive(x, pattern_except=pat_except)).values

        msg = "前年まで生存。枯死？"
        errors.extend(
            [
                err_dat_t(self.plotid, tag_no[i], gbhyr[j], msg)
                for i, j in zip(*np.where(match_na))
                if j > 0 and alive[i, j - 1]
            ]
        )

        # dの次の値がnaあるいはddになっていない
        pat_d = re.compile(r"^d$")
        match_d = df_gbh.applymap(lambda x: find_pattern(x, pat_d)).values
        pat_dd = re.compile(r"^dd$|^na$|^NA$")
        match_dd = df_gbh.applymap(lambda x: find_pattern(x, pat_dd)).values

        msg = "枯死の次の調査時のgbhが「na」もしくは「dd」になっていない"
        errors.extend(
            [
                err_dat_t(self.plotid, tag_no[i], gbhyr[j], msg)
                for i, j in zip(*np.where(match_d))
                if j < (len(gbhyr) - 1) and not match_dd[i, j + 1]
            ]
        )

        # 成長量が基準より大きいあるいは小さい
        # NOTE: 前回の値にcd, vn, viが付く場合はスキップ
        values_cleaned = df_gbh.applymap(lambda x: isvalid(x, return_value=True)).values
        pat_vc = re.compile("^vi|^vn|^cd")
        match_vc = df_gbh.applymap(lambda x: find_pattern(x, pat_vc)).values

        for i, row in enumerate(values_cleaned):
            index_notnull = np.where(~np.isnan(row))[0]
            gbhdiff = np.diff(row[index_notnull])
            yrdiff = np.diff([int(x.replace("gbh", "")) for x in gbhyr[index_notnull]])

            excess = gbhdiff > yrdiff * 2.5 + 3.8
            minus = gbhdiff < -3.1
            index_excess = index_notnull[1:][excess]
            index_minus = index_notnull[1:][minus]

            msg = "成長量が基準値より大きい。測定ミス？"
            errors.extend(
                [
                    err_dat_t(self.plotid, tag_no[i], gbhyr[j], msg)
                    for j in index_excess
                    if not match_vc[i, j - 1]
                ]
            )

            msg = "成長量が基準値より小さい。測定ミス？"
            errors.extend(
                [
                    err_dat_t(self.plotid, tag_no[i], gbhyr[j], msg)
                    for j in index_minus
                    if not match_vc[i, j - 1]
                ]
            )

        # 新規加入個体（naの次のgbhが数値）のサイズが基準より大きい
        notnull = ~np.isnan(values_cleaned)
        msg = "新規加入個体だが、加入時のgbhが基準より大きいのため前回計測忘れの疑い"
        for i, j in zip(*np.where(match_na[:, :-1] & notnull[:, 1:])):
            yrdiff = np.diff([int(x.replace("gbh", "")) for x in gbhyr[[j, (j + 1)]]])[
                0
            ]
            if values_cleaned[i, j + 1] >= (15 + yrdiff * 2.5 + 3.8):
                target = "{}={}; {}={}".format(
                    gbhyr[j], values[i, j], gbhyr[j + 1], values[i, j + 1]
                )
                errors.append(err_dat_t(self.plotid, tag_no[i], target, msg))

        # ndがついている値で、前後の測定値と比較して成長量の基準に収まっている
        # NOTE: 最初か最後の調査の値にndがつく場合はスキップ
        pat_ndxx = re.compile(r"^nd\s?([0-9]+[.]?[0-9]*)")
        match_ndxx = df_gbh.applymap(lambda x: find_pattern(x, pat_ndxx)).values
        values_cleaned = df_gbh.applymap(
            lambda x: isvalid(x, re.compile("^nd"), return_value=True)
        ).values

        for i, row in enumerate(values_cleaned):
            if any(match_ndxx[i]):
                index_notnull = np.where(~np.isnan(row))[0]
                index_match_ndxx = np.where(match_ndxx[i])[0]

                gbhdiff = np.diff(row[index_notnull])
                yrdiff = np.diff(
                    [int(x.replace("gbh", "")) for x in gbhyr[index_notnull]]
                )

                in_range = (gbhdiff <= yrdiff * 2.5 + 3.8) & (gbhdiff >= -3.1)

                index_notnull[1:][in_range]
                index_match_ndxx

                msg = "誤って「nd: 測定間違い」となっている可能性あり"
                for jj in np.where(match_ndxx[i][index_notnull][1:])[0]:
                    j = index_notnull[jj + 1]
                    if (j < (len(gbhyr) - 1)) and (jj < (len(in_range) - 1)):
                        if all(in_range[jj : (jj + 2)]):
                            errors.append(
                                err_dat_t(self.plotid, tag_no[i], gbhyr[j], msg)
                            )

        # 例外リストにあるエラー項目を除外
        except_list = self.get_except_list()
        if except_list:
            errors = [e for e in errors if e not in except_list]

        return errors

    def _check_data_litter(self, thoroughly=False):
        """リターデータのチェック"""
        errors = []

        # 日付の不正な入力
        s_date1 = self.df["s_date1"].values
        s_date2 = self.df["s_date2"].values
        trap_id = self.df["trap_id"].values

        s_date1_invalid = np.where(~np.vectorize(isdate)(s_date1))[0]
        s_date2_invalid = np.where(~np.vectorize(isdate)(s_date2))[0]

        msg = "s_date1に不正な入力値"
        errors.extend(
            [
                err_dat_l(self.plotid, s_date1[i], trap_id[i], msg)
                for i in s_date1_invalid
            ]
        )

        msg = "s_date2に不正な入力値"
        errors.extend(
            [
                err_dat_l(self.plotid, s_date1[i], trap_id[i], msg)
                for i in s_date2_invalid
            ]
        )

        # 日付に不正な入力値がある場合はここで終了
        if errors:
            print("日付に不正な入力値")
            return errors

        # 同じ設置・回収日でトラップの重複・欠落がないか
        # NOTE: 同じ時期でも数日に分けて回収した場合などもあり、必ずしもエラーではない
        path_traplist = self.fd.joinpath("suppl_data", "litter_trap_list.csv")
        df_traplist = read_file(path_traplist)
        df_traplist_s = df_traplist[df_traplist["plotid"] == self.plotid]
        trap_list = df_traplist_s["trap_id"].values

        period = s_date1 + "-" + s_date2
        for period_s, n_trap in zip(*np.unique(period, return_counts=True)):
            s_date1_s, s_date2_s = period_s.split("-")
            trap_s = trap_id[np.where(period == period_s)[0]]
            trap_dup = find_duplicates(trap_s)
            if trap_dup.size > 0:
                msg = "同じ設置・回収日の組み合わせでトラップの重複あり"
                msg += " ({})".format("; ".join(trap_dup))
                errors.append(err_dat_l(self.plotid, s_date1_s, "", msg))

            if n_trap < len(trap_list):
                msg = "同じ設置・回収日の組み合わせでトラップの欠落あり"
                trap_luck = [x for x in trap_list if x not in trap_s]
                msg += " ({})".format(";".join(trap_luck))
                errors.append(err_dat_l(self.plotid, s_date1_s, "", msg))

        # 設置期間に関するエラー
        s_date1_s, s_date2_s = zip(*[p.split("-") for p in np.unique(period)])
        s_date1_s, s_date2_s = np.array(s_date1_s), np.array(s_date2_s)
        s_date1_s_dt = np.array(list(map(as_datetime, s_date1_s)))
        s_date2_s_dt = np.array(list(map(as_datetime, s_date2_s)))
        delta_days = s_date2_s_dt - s_date1_s_dt
        delta_days = np.vectorize(calc_delta_days)(s_date1_s_dt, s_date2_s_dt)

        # 設置期間が長い
        long_d = delta_days > 45
        overwinter = ["UR-BC1", "AS-DB1", "AS-DB2", "TM-DB1"]
        overwinter += ["OY-DB1", "KY-DB1", "OT-EC1", "OG-DB1"]
        within_year = np.array(
            [i.year == j.year for i, j in zip(s_date1_s_dt, s_date2_s_dt)]
        )
        msg = "設置期間が46日以上"
        if self.plotid in overwinter:
            errors.extend(
                [
                    err_dat_l(self.plotid, d1, "", msg)
                    for d1 in s_date1_s[long_d & within_year]
                ]
            )
        else:
            errors.extend(
                [err_dat_l(self.plotid, d1, "", msg) for d1 in s_date1_s[long_d]]
            )

        # 設置期間が短い
        short_d = delta_days < 11
        msg = "設置期間が10日以下"
        errors.extend(
            [err_dat_l(self.plotid, d1, "", msg) for d1 in s_date1_s[short_d]]
        )

        # 設置期間がトラップによって異なる
        msg = "設置期間がトラップによって異なる"
        errors.extend(
            [
                err_dat_l(self.plotid, d1, "", msg)
                for d1 in np.unique(s_date1_s)
                if len(s_date2_s[s_date1_s == d1]) > 1
            ]
        )

        # 設置日と前回の回収日にずれ
        for trap in np.unique(trap_id):
            s_date1_s = s_date1[trap_id == trap]
            s_date2_s = s_date2[trap_id == trap]
            s_date1_s_dt = np.array(list(map(as_datetime, s_date1_s)))
            s_date2_s_dt = np.array(list(map(as_datetime, s_date2_s)))

            delta_days = np.vectorize(calc_delta_days)(
                s_date2_s_dt[:-1], s_date1_s_dt[1:]
            )

            interrupted = (delta_days != 0) & (delta_days < 45)
            within_year = np.array(
                [i.year == j.year for i, j in zip(s_date2_s_dt[:-1], s_date1_s_dt[1:])]
            )

            msg = "前回の回収日から{}日間の中断期間"
            errors.extend(
                [
                    err_dat_l(
                        self.plotid, s_date1_s[i + 1], trap, msg.format(delta_days[i])
                    )
                    for i in np.where(interrupted & within_year)[0]
                ]
            )

        # 測定値に関するエラー
        df_w = self.df.filter(regex="^w_|^wdry_").copy()

        # wdry_, w_データに含まれる記号
        # "na": "測定対象外", "nd": "欠損またはエラー", "-": "測定精度（大体0.01g）以下"
        s_except = "^NA$|^na$|^nd|-"
        pat_except = re.compile(s_except)

        s_date1 = self.df["s_date1"].values
        trap_id = self.df["trap_id"].values
        columns = df_w.columns.values
        values = df_w.values

        # 無効な入力値
        valid = df_w.applymap(lambda x: isvalid(x, pat_except))
        msg = "無効な入力値 ({}={})"
        errors.extend(
            [
                err_dat_l(
                    self.plotid,
                    s_date1[i],
                    trap_id[i],
                    msg.format(columns[j], values[i, j]),
                )
                for i, j in zip(*np.where(~valid))
            ]
        )

        # 無効な入力値はNaNに置換
        df_w = df_w[valid]

        # wdryについて器官・回収日ごとにスミルノフグラブス検定により外れ値の可能性がある値を検出
        # 数値以外の文字列はnanに置換
        # 0が多い月はそれ以外の値が外れ値になるので、0も除外
        df_wdry = df_w.filter(regex="^wdry_").copy()
        df_wdry = df_wdry.replace("^0$", np.nan, regex=True)
        values_cleaned = df_wdry.applymap(
            lambda x: isvalid(x, return_value=True)
        ).values

        msg = "{}は外れ値の可能性あり"
        for period_s in np.unique(period):
            d1 = period_s.split("-")[0]
            values_s = values_cleaned[period == period_s]
            trap_id_s = trap_id[period == period_s]

            for j, vals in enumerate(np.transpose(values_s)):
                if np.sum(~np.isnan(vals)) < 5:
                    continue

                outlier = smirnov_grubbs(np.log(vals))

                errors.extend(
                    [
                        err_dat_l(self.plotid, d1, trap_id_s[i], msg.format(columns[j]))
                        for i in np.where(outlier)[0]
                    ]
                )

        # 例外リストにあるエラー項目を除外
        except_list = self.get_except_list()
        if except_list:
            errors = [e for e in errors if e not in except_list]

        return errors

    def _check_data_seed(self, thoroughly=False):
        """種子データのチェック"""
        errors = []

        # 日付の不正な入力
        s_date1 = self.df["s_date1"].values
        s_date2 = self.df["s_date2"].values
        trap_id = self.df["trap_id"].values

        s_date1_invalid = np.where(~np.vectorize(isdate)(s_date1))[0]
        s_date2_invalid = np.where(~np.vectorize(isdate)(s_date2))[0]

        msg = "s_date1に不正な入力値"
        errors.extend(
            [
                err_dat_l(self.plotid, s_date1[i], trap_id[i], msg)
                for i in s_date1_invalid
            ]
        )

        msg = "s_date2に不正な入力値"
        errors.extend(
            [
                err_dat_l(self.plotid, s_date1[i], trap_id[i], msg)
                for i in s_date2_invalid
            ]
        )

        # 種名に関するエラー
        # 種名リストにない
        path_splist = self.fd.joinpath("suppl_data", "seed_species_list.csv")
        df_splist = read_file(path_splist)
        splist_all = df_splist.name_jp.values
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
                    outfile.write(self.plotid + "," + sp + "\n")
                msg = "{}はモニ1000種リストにない".format(sp)
                for i in self.df[self.df["spc"] == sp].itertuples():
                    errors.append(err_dat_l(self.plotid, i.trap_id, i.s_date1, msg))

            outfile.close()

        # 同種が２つ以上の名前で入力されている
        sp_in_list = df_splist[df_splist["name_jp"].isin(splist)]
        dups = [sp for sp, n in sp_in_list["species"].value_counts().items() if n > 1]
        for sp in dups:
            synonyms = sp_in_list[sp_in_list["species"] == sp]["name_jp"].tolist()
            msg = "同種が2つの名前で入力 ({})".format("/".join(synonyms))
            errors.append(err_dat_l(self.plotid, "", "", msg))

        # 非標準和名
        # NOTE: thoroughly=Trueの場合のみチェック
        if thoroughly:
            for sp, spstd in zip(sp_in_list["name_jp"], sp_in_list["name_jp_std"]):
                if spstd is not np.nan:
                    msg = "{}は非標準和名（{}の別名）".format(sp, spstd)
                    errors.append(err_dat_l(self.plotid, "", "", msg))

        # トラップリストとの整合性チェック
        path_traplist = self.fd.joinpath("suppl_data", "litter_trap_list.csv")
        df_traplist = read_file(path_traplist)
        df_traplist_s = df_traplist[df_traplist["plotid"] == self.plotid]
        trap_list = df_traplist_s["trap_id"].tolist()

        trap_uniq = self.df["trap_id"].unique()
        trap_not_in_list = [i for i in trap_uniq if i not in trap_list]
        for trap in trap_not_in_list:
            msg = "リストにないtrap_id".format(trap)
            for i in self.df[self.df["trap_id"] == trap].itertuples():
                errors.append(err_dat_l(self.plotid, trap, i.s_date1, msg))

        # 測定値に関するエラー
        df_w = self.df.filter(regex="^number|^w").copy()

        # number, wdryデータに含まれる記号
        # "na": "測定対象外", "nd": "欠損またはエラー", "-": "測定精度（大体0.01g）以下"
        s_except = "^NA$|^na$|^nd|-"
        pat_except = re.compile(s_except)

        s_date1 = self.df["s_date1"].values
        trap_id = self.df["trap_id"].values
        columns = df_w.columns.values
        values = df_w.values

        # 無効な入力値
        valid = df_w.applymap(lambda x: isvalid(x, pat_except))
        msg = "無効な入力値 ({}={})"
        errors.extend(
            [
                err_dat_l(
                    self.plotid,
                    s_date1[i],
                    trap_id[i],
                    msg.format(columns[j], values[i, j]),
                )
                for i, j in zip(*np.where(~valid))
            ]
        )

        # 無効な入力値はNaNに置換
        df_w = df_w[valid]

        # 例外リストにあるエラー項目を除外
        except_list = self.get_except_list()
        if except_list:
            errors = [e for e in errors if e not in except_list]

        return errors

    def check_data(self, thoroughly=False):
        if self.data_type == "tree":
            errors = self._check_data_tree(thoroughly)
        elif self.data_type == "litter":
            errors = self._check_data_litter(thoroughly)
        elif self.data_type == "seed":
            errors = self._check_data_seed(thoroughly)
        else:
            return
        return errors


def guess_data_type(df):
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


def save_errors_to_xlsx(errors, outfile, colnames, sortcol=""):
    """
    エラーリストをxlsx形式で出力
    """
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


def isvalid(s: str, pattern_except="", return_value=False):
    if isinstance(pattern_except, str):
        pattern_except = re.compile(pattern_except)

    try:
        s = pattern_except.sub("", str(s))
        f = float(np.nan if s == "" else s)
        return f if return_value else True
    except ValueError:
        return np.nan if return_value else True


def find_pattern(s: str, pattern):
    if isinstance(pattern, str):
        pattern = re.compile(pattern)

    if pattern.match(str(s)):
        return True
    else:
        return False


def isalive(s: str, gbh_threthold: float = 15, pattern_except=[]):
    if isvalid(s, pattern_except, return_value=True) >= gbh_threthold:
        return True
    else:
        return False


def isdate(s_date: str, nan_value=False):
    try:
        datetime.strptime(s_date, "%Y%m%d")
        return True
    except ValueError:
        return False
    except TypeError:
        return nan_value


def as_datetime(s_date, format="%Y%m%d"):
    if isdate(s_date, nan_value=False):
        return datetime.strptime(s_date, format)
    else:
        return np.datetime64("NaT")


def find_duplicates(array):
    uniq, counts = np.unique(array, return_counts=True)
    return uniq[counts > 1]


def dt64_to_dt(dt64):
    try:
        return datetime.strptime(dt64.astype("datetime64[D]").astype("str"), "%Y-%m-%d")
    except ValueError:
        return np.nan


def return_growth_year(dt):
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
    if isinstance(d1, datetime) and isinstance(d2, datetime):
        return (d2 - d1).days
    else:
        raise TypeError("d1 and d2 must be datetime.datetime objects")


def smirnov_grubbs(x, alpha=0.01):
    x = np.array(x)
    xs = x[~np.isnan(x)]
    i_out = np.array([], dtype=np.int64)
    
    while True:
        n = len(xs)
        if n < 5:
            break
        t = stats.t.isf(q=((alpha / n) / 2), df=(n - 2))
        tau = (n - 1) * t / np.sqrt(n * (n - 2) + n * t ** 2)
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


def run_data_check(filepath, outdir=""):
    filepath = Path(filepath)

    if not filepath.exists():
        errmsg = "{} not exists".format(filepath)
        raise FileNotFoundError(errmsg)

    if outdir:
        if isinstance(outdir, str):
            outdir = Path(outdir)
    else:
        outdir = filepath.parent

    if not outdir.exists:
        outdir.mkdir(parents=True, exist_ok=True)

    # データチェック
    mdf = Moni1000Data.from_file(filepath)
    print("Processing {}...".format(filepath.name))
    errors = mdf.check_data()

    if errors:
        if mdf.data_type == "tree":
            colnames = ["plotid", "tag_no", "エラー対象", "エラー内容"]
            sortcol = ["tag_no"]
        else:
            colnames = ["plotid", "s_date1", "trap_id", "エラー内容"]
            sortcol = ["s_date1", "trap_id"]

        outfile = filepath.parent.joinpath("確認事項{}.xlsx".format(filepath.stem))
        save_errors_to_xlsx(errors, outfile, colnames, sortcol)
        msg = "Output file {} was created.".format(outfile.name)
    else:
        msg = "No error detected."

    print(msg)
    
    
if __name__ == "__main__":
    import sys
    import time

    try:
        t1 = time.time()
        filepath = sys.argv[1]
        run_data_check(filepath)
        t2 = time.time()
        print("Done (elapsed time: {} sec.)".format(round(t2 - t1, 2)))
        sys.exit(0)
    except IndexError:
        sys.exit("Usage: python3 data_check.py DATAFILE")