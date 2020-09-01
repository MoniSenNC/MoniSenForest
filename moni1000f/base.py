import csv
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Union

import numpy as np
from openpyxl import load_workbook


class MonitoringData(object):
    """
    Data class for working with ecosystem monitoring data, paticularly in the
    data format of the Monitoring Sites 1000 projects.

    Parameters
    ----------
    data: numpy ndarray
        Two-dimensional numpy ndarray of the data
    plot_id: str, optional
        Plot ID
    metadata: dict, optional
        Metadata for the input data
    header: bool, default True
        If the input data includes a header line

    Attributes
    ----------
    data: numpy ndarray
        Data
    values: numpy ndarray
        Data values
    columns: list
        List of column names
    plot_id: str
        Plot ID
    data_type: str
        Data type guessed from the header line: tree, litter, seed, other
    metadata: dict
        Metadata
    """
    def __init__(self,
                 data: np.ndarray = np.array([]),
                 header: bool = True,
                 plot_id: str = "",
                 data_type: str = "",
                 metadata: Dict[str, str] = {},
                 *args,
                 **kwargs):

        self.data = data
        self.plot_id = plot_id
        if len(data) > 1:
            self.header = header
        else:
            self.header = False
        if data_type:
            self.data_type = data_type
        else:
            self.data_type = self.__guess_data_type()
        self.metadata = metadata

    @property
    def values(self):
        if self.header:
            return self.data[1:]
        else:
            return self.data

    @property
    def columns(self):
        if self.header:
            return self.data[0]
        else:
            return np.array([])

    def __repr__(self):
        s1 = "data_shape={}".format(self.values.shape)
        s2 = "plot_id={!r}".format(self.plot_id) if self.plot_id else ""
        s3 = "data_type={!r}".format(self.data_type) if self.data_type else ""
        s = ", ".join([i for i in (s1, s2, s3) if i])
        return "{}({})".format(self.__class__.__name__, s)

    def __getitem__(self, key):
        if isinstance(key, str):
            data_s = self.select_cols(key, add_header=True)
        elif isinstance(key, list) and all([isinstance(i, str) for i in key]):
            data_s = self.select_cols(key, add_header=True)
        elif isinstance(key, slice):
            data_s = np.vstack((self.columns, self.values[key]))
        elif isinstance(key, tuple) and all([isinstance(i, slice) for i in key]):
            data_s = np.vstack((self.columns[key[1]], self.values[key]))
        elif isinstance(key, int):
            data_s = np.vstack((self.columns, self.values[key]))
        else:
            pass
        return self.__getitem_return(data_s,
                                     header=self.header,
                                     plot_id=self.plot_id,
                                     data_type=self.data_type,
                                     metadata=self.metadata)

    @classmethod
    def __getitem_return(cls, data, **kwargs):
        return cls(data, **kwargs)

    def __guess_data_type(self):
        """Guess data type from the header line of the data."""
        cols_t = [
            "tag_no",
            "indv_no",
            "spc_japan",
            "^gbh[0-9]{2}$",
            "^s_date[0-9]{2}$",
        ]

        cols_l = [
            "^trap_id$",
            "^s_date1$",
            "^s_date2$",
            "^wdry_",
            "^w_",
        ]

        cols_s = [
            "^trap_id$",
            "^s_date1$",
            "^s_date2$",
            "^w",
            "^spc$",
            "^status$",
            "^form$",
        ]

        if all([any(filter(lambda x: re.match(i, x), self.columns)) for i in cols_t]):
            data_type = "tree"
        elif all([any(filter(lambda x: re.match(i, x), self.columns)) for i in cols_l]):
            data_type = "litter"
        elif all([any(filter(lambda x: re.match(i, x), self.columns)) for i in cols_s]):
            data_type = "seed"
        else:
            data_type = "other"

        return data_type

    def select_cols(self,
                    col: Union[str, List[str], None] = None,
                    regex: Union[str, None] = None,
                    add_header: bool = False) -> np.ndarray:
        """
        Select a data columns.

        Paramters
        ---------
        col: str, list, optional
            Column name(s) to select
        regex: str
            Regular expression pattern. Columns will be selected if the column names
            matches with the regular expression pattern
        add_header: bool, default False
            Add a header row to an output array
        """
        start = 1 if (self.header and not add_header) else 0

        if not self.header:
            raise RuntimeError("The data does not have column names")

        if regex:
            r = re.compile(regex)
            match = np.vectorize(lambda x: True if r.match(x) else False)(self.columns)
            selected = self.data[start:, match]

        elif col:
            if isinstance(col, str):
                col = [col]
            isin = np.isin(col, self.columns)
            if all(isin):
                selected = self.data[start:, np.isin(self.columns, col)]
            else:
                notin = ", ".join(np.array(col)[~isin])
                s = "s" if (~isin).sum() > 1 else ""
                msg = "Undefined column{}: {}".format(s, notin)
                raise KeyError(msg)

        else:
            raise RuntimeError("col or regex is needed")

        if not add_header and selected.shape[1] == 1:
            selected = selected.flatten()

        return selected


def read_file(filepath: str) -> np.ndarray:
    """
    Read a data file (.csv or .xlsx) and return a np.ndarray object.

    データファイルの読み込み。全て文字列として読み込む。

    Parameters
    ----------
    filepath: str
        path to the data file
    """
    suffix = Path(filepath).suffix
    if suffix == ".xlsx":
        wb = load_workbook(filepath)
        if "Data" in wb.sheetnames:
            ws = wb["Data"]
        else:
            ws = wb[wb.sheetnames[0]]
        data = np.array([[str(j) if j is not None else "" for j in i]
                         for i in ws.values])
    elif suffix == ".csv":
        with open(filepath) as f:
            reader = csv.reader(f)
            data = np.array([i for i in reader])
    else:
        msg = ("{} file is not supported. Supported formats are: "
               ".csv, .xlsx, .xlsm, .xltx, .xltm").format(suffix)
        raise RuntimeError(msg)

    # remove blank rows/columns
    is_blank = np.where(data == "", True, False)
    data = data[:, ~is_blank.all(axis=0)]
    data = data[~is_blank.all(axis=1), :]

    return data


def split_comments(data: np.ndarray,
                   comment: str = "#") -> Tuple[np.ndarray, np.ndarray]:
    """Split comment lines (rows) from data array."""
    if comment:
        com_rows = np.vectorize(lambda x: str(x).startswith(comment))(data[:, 0])
        comments = data[com_rows]
        data = data[~com_rows]
    else:
        comments = np.array([], dtype=data.dtype)

    return data, comments


def get_metadata(comments: np.ndarray) -> Dict[str, str]:
    """Get metadata from comment lines."""
    keys = [
        'DATA CREATED', 'DATA CREATER', 'DATA TITLE', 'SITE NAME', 'PLOT NAME',
        'PLOT ID', 'PLOT SIZE', 'NO. OF TRAPS', 'TRAP SIZE'
    ]
    metadata = {}
    for key in keys:
        match = list(zip(*np.where(comments == key)))
        if match:
            i, j = match[0]
            metadata[key] = comments[i, j + 2]
    return metadata


def get_plotid(filepath: str) -> str:
    """
    Get the plot id from a file name.

    Parameter
    ---------
    filepath: str
        path of a data file
    """
    filepath = Path(filepath)
    ftype = ["AT", "EC", "BC", "EB", "DB"]
    r = re.compile("|".join(["[A-Z]{{2}}-{}[0-9]".format(i) for i in ftype]))
    try:
        return r.search(filepath.name).group()
    except AttributeError:
        return ""


def read_data(filepath: str, comment: str = "#", header: bool = True) -> MonitoringData:
    """
    Read a data file and return a MonitoringData object.

    Parameters
    ----------
    filepath: str
        Path to the data file. Supported formats are: .csv, .xlsx, .xlsm, .xltx, .xltm
    comment: str, default "#"
        Character to detect commented lines. If found at the beginning of  a line, the
        line will be parsed as commented lines and split from remaing data
    header: bool, default True
        If the parsed data includes a header line
    """
    data = read_file(filepath)
    data, comments = split_comments(data, comment)

    if len(comments) > 0:
        metadata = get_metadata(comments)
    else:
        metadata = {}

    if "PLOT ID" in metadata:
        plot_id = metadata["PLOT ID"]
    else:
        plot_id = get_plotid(filepath)

    return MonitoringData(data, plot_id=plot_id, metadata=metadata, header=header)


def clean_data(data: np.ndarray) -> np.ndarray:
    """
    Clean up the data.

    Remove white spaces, line breaks, normalize unocode characters etc.).

    Parameters
    ----------
    data: numpy ndarray
        Two dimentional array with the dtype of string('<U')
    """
    # 不要な空白を削除
    data = np.vectorize(lambda x: x.strip())(data)
    # unicode文字列の標準化（全角英数字->半角英数字, 半角カナ->全角カナ, etc.）
    data = np.vectorize(lambda x: unicodedata.normalize("NFKC", x))(data)
    # float型で小数点以下が長くなっている値を丸める
    data = np.vectorize(clean_float)(data)
    # datetime型の文字列をyyyymmdd形式の文字列に変換
    data = np.vectorize(datetime_to_yyyymmdd)(data)
    # セル内改行・タブ・垂直タブ・改頁を削除
    data = np.vectorize(lambda x: re.sub("\r\n|\n|\r|\t|\x0b|\x0c", "", x))(data)

    return data


def clean_float(x: Union[str, float, int]) -> str:
    """
    Floating-point rounding.

    小数点以下が長い場合は丸める。
    """
    try:
        int(x)
    except ValueError:
        try:
            return str(float(x))
        except ValueError:
            return str(x)
    else:
        return str(x)


def datetime_to_yyyymmdd(s: str) -> str:
    """
    Convert a datetime string to a string in the yyyymmdd format.

    日付がyyyymmddになっていない場合修正。
    """
    pat_datetime = re.compile(r"(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})")
    m = pat_datetime.match(str(s))
    if m:
        dt = datetime.strptime(m.group(), "%Y-%m-%d %H:%M:%S")
        s = datetime.strftime(dt, "%Y%m%d")
    return s


def file_to_csv(filepath: str, outdir: str = None, cleaning: bool = True):
    """
    Clean data of a tabular input file and export as a csv file.

    Excel/CSVファイルを読み込み、クリーニング後、CSVファイルとして書き出す。

    Parameters
    ----------
    filepath : str
        Path to the data file
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
    outpath = outdir.joinpath(basename + ".csv")

    data = read_file(filepath)
    if cleaning:
        data = clean_data(data)
    with open(outpath, "w") as f:
        writer = csv.writer(f, delimiter=",", quotechar='"', quoting=csv.QUOTE_MINIMAL)
        for row in data:
            writer.writerow(row)
