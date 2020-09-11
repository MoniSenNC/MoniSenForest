import json
import logging
import queue
import re
import signal
import threading
import time
import tkinter as tk
from logging.handlers import QueueHandler
from pathlib import Path
from tkinter import E, N, S, W, filedialog, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Optional

import numpy as np

from MoniSenForest.base import read_data
from MoniSenForest.datacheck import check_data, save_errors_to_xlsx
from MoniSenForest.tree_data_transform import add_state_columns

logger = logging.getLogger(__name__)
logger.propagate = False

fd = Path(__file__).resolve().parents[0]
path_spdict = fd.joinpath("suppl_data", "species_dict.json")
with open(path_spdict) as f:
    dict_sp = json.load(f)


class MainWindow(ttk.Frame):
    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        self.master = master
        self.master.title("MoniSenForest GUI")
        self.master.columnconfigure(0, weight=1)
        self.master.rowconfigure(0, weight=1)
        self.grid(row=0, column=0, sticky=(N, S, E, W))
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        # variables
        self.comment_chr = tk.StringVar(value="#")
        self.outdir = tk.StringVar()
        self.suffix = tk.StringVar()
        self.path_ignore = tk.StringVar()
        self.enc_in = tk.StringVar(value="utf-8")
        self.enc_out = tk.StringVar(value="utf-8")
        self.keep_comments = tk.BooleanVar(value=True)
        self.clean = tk.BooleanVar(value=True)
        self.add_sciname = tk.BooleanVar(value=False)
        self.add_class = tk.BooleanVar(value=False)
        self.add_status = tk.BooleanVar(value=False)

        self.pane1 = ttk.Panedwindow(self, orient=tk.HORIZONTAL)
        self.pane2 = ttk.Panedwindow(self, orient=tk.VERTICAL)
        self.pane1.grid(row=0, column=0, sticky=(N, S, E, W))
        self.pane2.grid(row=0, column=0, sticky=(N, S, E, W))

        self.frame1 = CommandFrame(self, text="Commands")
        self.frame2 = LoggerFrame(self, text="Messages")
        self.frame3 = SettingFrame(self, text="Settings")

        self.pane1.add(self.frame1, weight=1)
        self.pane1.add(self.pane2, weight=1)
        self.pane2.add(self.frame2, weight=1)
        self.pane2.add(self.frame3, weight=1)

        self.worker1 = None
        self.worker2 = None
        self.worker3 = QueueCheckWorker(self)
        self.worker3.start()
        self.th_active_init = threading.active_count()

        self.master.protocol("WM_DELETE_WINDOW", self.quit)
        self.master.bind("<Control-q>", self.quit)
        signal.signal(signal.SIGINT, self.quit)

    def quit(self, *args):
        if self.worker1 and self.worker1.is_alive():
            self.worker1.stop()
        if self.worker2 and self.worker2.is_alive():
            self.worker2.stop()
        self.worker3.stop()
        self.master.destroy()

    def stop(self):
        if threading.active_count() == self.th_active_init:
            logger.warning("There are no ongoing processes.")
        if self.worker1 and self.worker1.is_alive():
            self.worker1.stop()
        if self.worker2 and self.worker2.is_alive():
            self.worker2.stop()


class CommandFrame(ttk.Labelframe):
    def __init__(self, parent=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.parent = parent
        self.current_dir = Path("~").expanduser()
        self.filepaths = []
        self._btn4_disabled = True
        self.columnconfigure(0, weight=1)
        self.create_widgets()

    def create_widgets(self):
        self.btn1 = ttk.Button(self, text="Select Data Files")
        self.btn1["command"] = self.btn1_pushed
        self.btn2 = ttk.Button(self, text="Export CSV", state="disabled")
        self.btn2["command"] = self.btn2_pushed
        self.btn3 = ttk.Button(self, text="Check Data", state="disabled")
        self.btn3["command"] = self.btn3_pushed
        self.btn4 = ttk.Button(self, text="Stop", state="disabled")
        self.btn4["command"] = self.parent.stop
        self.btn5 = ttk.Button(self, text="Quit")
        self.btn5["command"] = self.parent.quit

        self.btn1.grid(row=0, column=0, sticky=(E, W), padx=5, pady=5)
        self.btn2.grid(row=1, column=0, sticky=(E, W), padx=5, pady=5)
        self.btn3.grid(row=2, column=0, sticky=(E, W), padx=5, pady=5)
        self.btn4.grid(row=3, column=0, sticky=(E, W), padx=5, pady=5)
        self.btn5.grid(row=4, column=0, sticky=(E, W), padx=5, pady=5)

    def btn1_pushed(self):
        selected = filedialog.askopenfilenames(
            filetypes=[
                ("EXCEL/CSV files", "*.xlsx"),
                ("EXCEL/CSV files", "*.csv"),
                ("All files", "*.*"),
            ],
            initialdir=self.current_dir,
            title="Select Data Files",
        )

        if selected:
            if self.filepaths:
                self.filepaths = []
            self.filepaths = [p for p in selected]
            nfile = len(self.filepaths)
            msg = "{} file{} selected.".format(nfile, "" if nfile == 1 else "s")
            logger.info(msg)

            # Remember the directory at the last filedialog operation
            parentdir = Path(self.filepaths[0]).parent
            if str(parentdir) != str(self.current_dir):
                self.current_dir = parentdir

        if self.filepaths:
            self.btn2["state"] = "normal"
            self.btn3["state"] = "normal"
        else:
            self.btn2["state"] = "disabled"
            self.btn3["state"] = "disabled"

    def btn2_pushed(self):
        if self.parent.worker1 and self.parent.worker1.is_alive():
            logger.warning("Data exporting process is still running")
            return

        self.parent.worker1 = FileExportWorker(
            self.filepaths,
            outdir=self.parent.outdir.get(),
            suffix=self.parent.suffix.get(),
            enc_in=self.parent.enc_in.get(),
            add_sciname=self.parent.add_sciname.get(),
            add_class=self.parent.add_class.get(),
            add_status=self.parent.add_status.get(),
            cleaning=self.parent.clean.get(),
            keep_comments=self.parent.keep_comments.get(),
            encoding=self.parent.enc_out.get(),
        )
        self.parent.worker1.start()
        if self._btn4_disabled:
            self.btn4["state"] = "normal"
            self._btn4_disabled = False

    def btn3_pushed(self):
        if self.parent.worker2 and self.parent.worker2.is_alive():
            logger.warning("Data checking process is still running")
            return

        self.parent.worker2 = DataCheckWorker(
            self.filepaths,
            outdir=self.parent.outdir.get(),
            enc_in=self.parent.enc_in.get(),
            path_ignore=self.parent.path_ignore.get(),
        )
        self.parent.worker2.start()
        if self._btn4_disabled:
            self.btn4["state"] = "normal"
            self._btn4_disabled = False

    def btn4_state_set(self):
        if threading.active_count() == self.parent.th_active_init:
            self.btn4["state"] = "disabled"
            self._btn4_disabled = True
        elif self._btn4_disabled:
            self.btn4["state"] = "normal"
            self._btn4_disabled = False


class LoggerFrame(ttk.LabelFrame):
    def __init__(self, parent=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.parent = parent
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.create_widgets()
        self.create_logginghandler()
        logger.info("Welcome to the MoniSenForest Application!")

    def create_widgets(self):
        self.scrolled_text = ScrolledText(self, state="disabled", height=12)
        self.scrolled_text.grid(row=0, column=0, sticky=(N, S, E, W))
        self.scrolled_text.configure(font="TkFixedFont")
        self.scrolled_text.tag_config("INFO", foreground="black")
        self.scrolled_text.tag_config("DEBUG", foreground="gray")
        self.scrolled_text.tag_config("WARNING", foreground="orange")
        self.scrolled_text.tag_config("ERROR", foreground="red")
        self.scrolled_text.tag_config("CRITICAL", foreground="red", underline=1)

    def create_logginghandler(self):
        self.log_queue = queue.Queue()
        self.queue_handler = QueueHandler(self.log_queue)
        formatter = logging.Formatter("%(asctime)s - %(message)s", "%Y-%m-%d %H:%M:%S")
        self.queue_handler.setFormatter(formatter)
        logger.addHandler(self.queue_handler)

    def check_queue(self):
        while True:
            try:
                record = self.log_queue.get(block=False)
            except queue.Empty:
                break
            else:
                self.print_log(record)

    def print_log(self, record):
        msg = record.getMessage()
        self.scrolled_text.configure(state="normal")
        self.scrolled_text.insert(tk.END, msg + "\n", record.levelname)
        self.scrolled_text.configure(state="disabled")
        self.scrolled_text.yview(tk.END)


class SettingFrame(ttk.LabelFrame):
    def __init__(self, parent=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.parent = parent
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        # Create a notebook
        self.nb = ttk.Notebook(self)
        self.nb.grid(column=0, row=0, sticky=(N, S, E, W))
        self.tab1 = ttk.Frame(self)
        self.tab2 = ttk.Frame(self)
        self.tab3 = ttk.Frame(self)
        self.tab1.columnconfigure(1, weight=1)
        self.tab2.columnconfigure(1, weight=1)
        self.tab3.columnconfigure(1, weight=1)
        self.nb.add(self.tab1, text="Import")
        self.nb.add(self.tab2, text="Export")
        self.nb.add(self.tab3, text="Data Check")
        self.create_widgets1()
        self.create_widgets2()
        self.create_widgets3()

    def create_widgets1(self):
        self.lab11 = ttk.Label(self.tab1, text="Comment character: ")
        self.wg11 = ttk.Frame(self.tab1)
        self.wg11_entry = ttk.Entry(self.wg11, textvariable=self.parent.comment_chr)
        self.lab11.grid(column=0, row=0, sticky=(E, W), padx=5, pady=5)
        self.wg11.grid(column=1, row=0, sticky=(E, W), padx=5, pady=5)
        self.wg11_entry.grid(column=0, row=0, sticky=(E, W), padx=5, pady=2)

        # self.lab12 = ttk.Label(self.tab1, text="Text encoding (csv):")
        # self.wg12 = ttk.Frame(self.tab1)
        # self.wg12_rb1 = ttk.Radiobutton(
        #     self.wg12, text="UTF-8", value="utf-8", variable=self.parent.enc_in
        # )
        # self.wg12_rb2 = ttk.Radiobutton(
        #     self.wg12, text="Shift-JIS", value="shift-jis", variable=self.parent.enc_in
        # )
        # self.lab12.grid(column=0, row=1, sticky=(E, W), padx=5, pady=5)
        # self.wg12.grid(column=1, row=1, sticky=(E, W), padx=5, pady=5)
        # self.wg12_rb1.grid(column=0, row=0, sticky=(E, W), padx=5, pady=2)
        # self.wg12_rb2.grid(column=1, row=0, sticky=(E, W), padx=5, pady=2)

    def create_widgets2(self):
        self.lab21 = ttk.Label(self.tab2, text="Output directory:")
        self.wg21 = ttk.Frame(self.tab2)
        self.wg21.columnconfigure(0, weight=1)
        self.wg21_entry = ttk.Entry(self.wg21, textvariable=self.parent.outdir)
        self.wg21_btn = ttk.Button(self.wg21, text="...", command=self.btn21_pushed)
        self.wg21_lab = ttk.Label(self.wg21, text="(optional)")
        self.lab21.grid(column=0, row=0, sticky=(E, W), padx=5, pady=5)
        self.wg21.grid(column=1, row=0, sticky=(E, W), padx=5, pady=5)
        self.wg21_entry.grid(column=0, row=1, sticky=(E, W), padx=5, pady=2)
        self.wg21_btn.grid(column=1, row=1, sticky=(E, W), padx=5, pady=2)
        self.wg21_lab.grid(column=2, row=1, sticky=(E, W), padx=5, pady=2)

        self.lab22 = ttk.Label(self.tab2, text="File name suffix:")
        self.wg22 = ttk.Frame(self.tab2)
        self.wg22_entry = ttk.Entry(self.wg22, textvariable=self.parent.suffix)
        self.wg22_lab = ttk.Label(self.wg22, text="(optional)")
        self.lab22.grid(column=0, row=1, sticky=(E, W), padx=5, pady=5)
        self.wg22.grid(column=1, row=1, sticky=(E, W), padx=5, pady=5)
        self.wg22_entry.grid(column=0, row=1, sticky=(E, W), padx=5, pady=2)
        self.wg22_lab.grid(column=1, row=1, sticky=(E, W), padx=5, pady=2)

        self.lab23 = ttk.Label(self.tab2, text="Text encoding:")
        self.wg23 = ttk.Frame(self.tab2)
        self.wg23_rb1 = ttk.Radiobutton(
            self.wg23, text="UTF-8", value="utf-8", variable=self.parent.enc_out
        )
        self.wg23_rb2 = ttk.Radiobutton(
            self.wg23, text="Shift-JIS", value="shift-jis", variable=self.parent.enc_out
        )
        self.lab23.grid(column=0, row=2, sticky=(E, W), padx=5, pady=5)
        self.wg23.grid(column=1, row=2, sticky=(E, W), padx=5, pady=5)
        self.wg23_rb1.grid(column=0, row=0, sticky=(E, W), padx=5, pady=2)
        self.wg23_rb2.grid(column=1, row=0, sticky=(E, W), padx=5, pady=2)

        self.lab24 = ttk.Label(self.tab2, text="Other options:")
        self.wg24 = ttk.Frame(self.tab2)
        self.wg24_cb1 = ttk.Checkbutton(
            self.wg24, text="Keep comment lines", variable=self.parent.keep_comments
        )
        self.wg24_cb2 = ttk.Checkbutton(
            self.wg24,
            text="Data cleaning (remove whitespaces, etc.)",
            variable=self.parent.clean,
        )
        self.wg24_cb3 = ttk.Checkbutton(
            self.wg24,
            text="Add scientific name (GBH/seed data)",
            variable=self.parent.add_sciname,
        )
        self.wg24_cb4 = ttk.Checkbutton(
            self.wg24,
            text="Add classification (GBH/seed data)",
            variable=self.parent.add_class,
        )
        self.wg24_cb5 = ttk.Checkbutton(
            self.wg24,
            text=(
                "Remove special characters and add error, death, recruit columns "
                "(GBH data)"
            ),
            variable=self.parent.add_status,
        )
        self.lab24.grid(column=0, row=3, sticky=(N, E, W), padx=5, pady=5)
        self.wg24.grid(column=1, row=3, sticky=(E, W), padx=5, pady=5)
        self.wg24_cb1.grid(column=0, row=0, sticky=(E, W), padx=5, pady=2)
        self.wg24_cb2.grid(column=0, row=1, sticky=(E, W), padx=5, pady=2)
        self.wg24_cb3.grid(column=0, row=2, sticky=(E, W), padx=5, pady=2)
        self.wg24_cb4.grid(column=0, row=3, sticky=(E, W), padx=5, pady=2)
        self.wg24_cb5.grid(column=0, row=4, sticky=(N, E, W), padx=5, pady=2)

    def create_widgets3(self):
        self.lab31 = ttk.Label(self.tab3, text="Output directory:")
        self.wg31 = ttk.Frame(self.tab3)
        self.wg31.columnconfigure(0, weight=1)
        self.wg31_entry = ttk.Entry(self.wg31, textvariable=self.parent.outdir)
        self.wg31_btn = ttk.Button(self.wg31, text="...", command=self.btn21_pushed)
        self.wg31_lab = ttk.Label(self.wg31, text="(optional)")
        self.lab31.grid(column=0, row=0, sticky=(E, W), padx=5, pady=5)
        self.wg31.grid(column=1, row=0, sticky=(E, W), padx=5, pady=5)
        self.wg31_entry.grid(column=0, row=1, sticky=(E, W), padx=5, pady=2)
        self.wg31_btn.grid(column=1, row=1, sticky=(E, W), padx=5, pady=2)
        self.wg31_lab.grid(column=2, row=1, sticky=(E, W), padx=5, pady=2)

        self.lab32 = ttk.Label(self.tab3, text="Ignore list:")
        self.wg32 = ttk.Frame(self.tab3)
        self.wg32.columnconfigure(0, weight=1)
        self.wg32_entry = ttk.Entry(self.wg32, textvariable=self.parent.path_ignore)
        self.wg32_btn = ttk.Button(self.wg32, text="...", command=self.btn32_pushed)
        self.wg32_lab = ttk.Label(self.wg32, text="(optional)")
        self.lab32.grid(column=0, row=1, sticky=(E, W), padx=5, pady=5)
        self.wg32.grid(column=1, row=1, sticky=(E, W), padx=5, pady=5)
        self.wg32_entry.grid(column=0, row=1, sticky=(E, W), padx=5, pady=2)
        self.wg32_btn.grid(column=1, row=1, sticky=(E, W), padx=5, pady=2)
        self.wg32_lab.grid(column=2, row=1, sticky=(E, W), padx=5, pady=2)

    def btn21_pushed(self):
        if not self.parent.outdir.get():
            initialdir = Path("~").expanduser()
        else:
            initialdir = self.parent.outdir.get()
        selected = filedialog.askdirectory(
            initialdir=initialdir, title="Select Output Directory",
        )
        self.parent.outdir.set(selected)

    def btn32_pushed(self):
        if not self.parent.path_ignore.get():
            initialdir = Path("~").expanduser()
        else:
            initialdir = Path(self.parent.path_ignore.get()).parent
        selected = filedialog.askopenfilename(
            filetypes=[
                ("EXCEL/CSV files", "*.xlsx"),
                ("EXCEL/CSV files", "*.csv"),
                ("All files", "*.*"),
            ],
            initialdir=initialdir,
            title="Select File",
        )
        self.parent.path_ignore.set(selected)


class DataCheckWorker(threading.Thread):
    def __init__(
        self,
        filepaths=None,
        outdir: Optional[str] = None,
        enc_in: str = "utf-8",
        **kwargs
    ):
        super().__init__()
        self._stop_event = threading.Event()
        self.filepaths = filepaths.copy()
        self.outdir = outdir
        self.enc_in = enc_in
        self.params = kwargs

    def run(self):
        if not self.filepaths:
            logger.warning("No data files selected")
            return

        logger.debug("Start data checking ...")
        while not self._stop_event.is_set() and self.filepaths:
            filepath = Path(self.filepaths.pop(0)).expanduser()
            logger.debug("Checking {} ...".format(filepath.name))

            try:
                d = read_data(filepath, encoding=self.enc_in)
            except UnicodeDecodeError:
                msg = "Can not decode {}. Make sure the file is encoded in UTF-8 (without BOM).".format(
                    filepath.name
                )
                logger.warning(msg)
                continue

            try:
                errors = check_data(d, **self.params)
            except TypeError:
                msg = "Skip {} which is not a MoniSen data file.".format(filepath.name)
                logger.warning(msg)
            except RuntimeError as e:
                logger.error(str(e))
                self._stop_event.set()
            else:
                if errors:
                    if self.outdir:
                        outdir = Path(self.outdir)
                        outdir.mkdir(parents=True, exist_ok=True)
                    else:
                        outdir = filepath.parent

                    outpath = outdir.joinpath("確認事項{}.xlsx".format(filepath.stem))
                    if d.data_type == "tree":
                        header = ["plotid", "tag_no", "target", "error_type"]
                    else:
                        header = ["plotid", "s_date1", "trap_id", "error_type"]
                    save_errors_to_xlsx(errors, outpath, header)
                    logger.info("{} is created.".format(outpath.name))
                else:
                    logger.debug("No errors detected.")
            time.sleep(0.1)

        if self._stop_event.is_set():
            msg = "Data checking process has been stopped."
            logger.warning(msg)
        else:
            logger.debug("Data checking finished.")

    def stop(self):
        self._stop_event.set()


class FileExportWorker(threading.Thread):
    """
    Export a data file as a csv file.

    Parameters
    ----------
    filepath : str
        Path to a data file
    outdir : str, default None
        Output directory
    suffix : str, default None
        Suffix of the output file name
    enc_in : str, default "utf-8"
        Text encoding for reading
    add_sciname : bool, default False
        If add a column of scientific names
    add_class : bool, default False
        If add columns of classifications
    add_status : bool, default False
        If add columns of status
    cleaning : bool, default True
        If clean up the data
    keep_comments : bool, default True
        If keep the comment lines
    encoding : str, default "utf-8"
        Text encoding for exporting

    """

    def __init__(
        self,
        filepaths=None,
        outdir: Optional[str] = None,
        suffix: Optional[str] = None,
        enc_in: str = "utf-8",
        add_sciname: bool = False,
        add_class: bool = False,
        add_status: bool = False,
        **kwargs
    ):
        super().__init__()
        self._stop_event = threading.Event()
        self.filepaths = filepaths.copy()
        self.outdir = outdir
        self.suffix = suffix
        self.enc_in = enc_in
        self.add_sciname = add_sciname
        self.add_class = add_class
        self.add_status = add_status
        self.params = kwargs

    def run(self):
        global dict_sp

        if not self.filepaths:
            logger.warning("No data files selected")
            return

        r = re.compile(r"^(.*)_\([0-9]+\)$")
        while not self._stop_event.is_set() and self.filepaths:
            filepath = Path(self.filepaths.pop(0)).expanduser()
            logger.debug("Exporting {} ...".format(filepath.name))

            if self.outdir:
                outdir = Path(self.outdir)
                outdir.mkdir(parents=True, exist_ok=True)
            else:
                outdir = filepath.parent

            basename = filepath.stem
            if self.suffix:
                outpath = outdir.joinpath(basename + self.suffix + ".csv")
            else:
                outpath = outdir.joinpath(basename + ".csv")
            if outpath.exists():
                m = r.match(outpath.stem)
                if m:
                    stem = m.group(1)
                else:
                    stem = outpath.stem
                i = 1
                while True:
                    outname = "{}_({}).csv".format(stem, i)
                    outpath = outdir.joinpath(outname)
                    if not outpath.exists():
                        break
                    i += 1

            try:
                d = read_data(filepath, encoding=self.enc_in)
            except UnicodeDecodeError:
                msg = "Can not decode {}. Make sure the file is encoded in UTF-8 (without BOM).".format(
                    filepath.name
                )
                logger.warning(msg)
                continue

            if d.data_type == "tree" and self.add_status:
                d = add_state_columns(d)

            if d.data_type in ["tree", "seed"] and self.add_sciname:
                sciname = []
                not_found = []
                for i in d.select_cols(regex="^spc_japan$|^spc$"):
                    if i in dict_sp:
                        sciname.append(dict_sp[i]["species"])
                    else:
                        sciname.append("")
                        not_found.append(i)
                if not_found:
                    for i in not_found:
                        msg = "{} not found in the species dictionary".format(i)
                        logger.warning(msg)
                d.data = np.vstack((d.data.T, np.append(["species"], sciname))).T

            if d.data_type in ["tree", "seed"] and self.add_class:
                cols = ["genus", "family", "order", "family_jp", "order_jp"]
                classification = []
                not_found = []
                for i in d.select_cols(regex="^spc_japan$|^spc$"):
                    if i in dict_sp:
                        classification.append([dict_sp[i][j] for j in cols])
                    else:
                        classification.append([""] * 5)
                        not_found.append(i)
                if not_found:
                    for i in not_found:
                        msg = "{} not found in the species dictionary".format(i)
                        logger.warning(msg)
                d.data = np.hstack((d.data, np.vstack((cols, classification))))

            d.to_csv(outpath, **self.params)

            logger.info("{} is created.".format(outpath.name))
            time.sleep(0.1)

        if self._stop_event.is_set():
            msg = "Data exporting process has been stopped by the user."
            logger.warning(msg)
        else:
            logger.debug("Data exporting finished.")

    def stop(self):
        self._stop_event.set()


class QueueCheckWorker(threading.Thread):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self._stop_event = threading.Event()

    def run(self):
        while not self._stop_event.is_set():
            self.parent.frame2.check_queue()
            self.parent.frame1.btn4_state_set()
            time.sleep(0.1)

    def stop(self):
        self._stop_event.set()


def main():
    logging.basicConfig(level=logging.DEBUG)
    root = tk.Tk()

    # a fix for running on OSX - to center the title text vertically
    if root.tk.call("tk", "windowingsystem") == "aqua":
        s = ttk.Style()
        s.configure("TNotebook.Tab", padding=(12, 8, 12, 0))

    app = MainWindow(master=root)
    app.master.mainloop()


if __name__ == "__main__":
    main()
