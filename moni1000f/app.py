import logging
import queue
import signal
import threading
import time
import tkinter as tk
from logging.handlers import QueueHandler
from pathlib import Path
from tkinter import N, S, E, W, filedialog, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Optional

from moni1000f.base import data_to_csv, read_data, read_file
from moni1000f.datacheck import check_data, save_errors_to_xlsx

logger = logging.getLogger(__name__)


class MainWindow(ttk.Panedwindow):
    def __init__(self, master=None, **kwargs):
        super().__init__(master, orient=tk.HORIZONTAL, **kwargs)
        self.master = master
        self.master.title('MoniSenForest')
        self.master.columnconfigure(0, weight=1)
        self.master.rowconfigure(0, weight=1)
        self.grid(row=0, column=0, sticky=(N, S, E, W))

        self.frame1 = CommandFrame(self, text="Commands")
        self.frame2 = LoggerFrame(self, text="Messages")
        self.add(self.frame1, weight=1)
        self.add(self.frame2, weight=1)

        self.worker1 = None
        self.worker2 = None
        self.worker3 = QueueCheckWorker(self)
        self.worker3.start()
        self.th_active_init = threading.active_count()

        self.master.protocol('WM_DELETE_WINDOW', self.quit)
        self.master.bind('<Control-q>', self.quit)
        signal.signal(signal.SIGINT, self.quit)

    def quit(self):
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
        self.btn1 = ttk.Button(self, text="Select Files")
        self.btn1["command"] = self.btn1_pushed
        self.btn2 = ttk.Button(self, text="Export as CSV", state="disabled")
        self.btn2["command"] = self.btn2_pushed
        self.btn3 = ttk.Button(self, text="Check Data", state="disabled")
        self.btn3["command"] = self.btn3_pushed
        self.btn4 = ttk.Button(self, text="Stop", state="disabled")
        self.btn4["command"] = self.parent.stop
        self.btn5 = ttk.Button(self, text="Quit")
        self.btn5["command"] = self.parent.quit

        self.btn1.grid(row=0, column=0, sticky=(E, W), padx=4, pady=4)
        self.btn2.grid(row=1, column=0, sticky=(E, W), padx=4, pady=4)
        self.btn3.grid(row=2, column=0, sticky=(E, W), padx=4, pady=4)
        self.btn4.grid(row=3, column=0, sticky=(S, E, W), padx=4, pady=4)
        self.btn5.grid(row=4, column=0, sticky=(S, E, W), padx=4, pady=4)

    def btn1_pushed(self):
        selected = filedialog.askopenfilenames(filetypes=[("EXCEL/CSV files", "*.xlsx"),
                                                          ("EXCEL/CSV files", "*.csv"),
                                                          ("All files", "*.*")],
                                               initialdir=self.current_dir,
                                               title="Select Data Files")

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
            logger.warning("Exporting process is still running")
            return

        self.parent.worker1 = FileConvertWorker(self.filepaths)
        self.parent.worker1.start()
        if self._btn4_disabled:
            self.btn4["state"] = "normal"
            self._btn4_disabled = False

    def btn3_pushed(self):
        if self.parent.worker2 and self.parent.worker2.is_alive():
            logger.warning("Data checking process is still running")
            return

        self.parent.worker2 = CheckDataWorker(self.filepaths)
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


class LoggerFrame(ttk.Labelframe):
    def __init__(self, parent=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.parent = parent
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.create_widgets()
        self.create_logginghandler()
        logger.info("Welcome to the MoniSenForest application!")

    def create_widgets(self):
        self.scrolled_text = ScrolledText(self, state="disabled", height=24)
        self.scrolled_text.grid(row=0, column=0, sticky=tk.NSEW)
        self.scrolled_text.configure(font='TkFixedFont')
        self.scrolled_text.tag_config('INFO', foreground='black')
        self.scrolled_text.tag_config('DEBUG', foreground='gray')
        self.scrolled_text.tag_config('WARNING', foreground='orange')
        self.scrolled_text.tag_config('ERROR', foreground='red')
        self.scrolled_text.tag_config('CRITICAL', foreground='red', underline=1)

    def create_logginghandler(self):
        self.log_queue = queue.Queue()
        self.queue_handler = QueueHandler(self.log_queue)
        formatter = logging.Formatter('%(asctime)s - %(message)s', "%Y-%m-%d %H:%M:%S")
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
        self.scrolled_text.configure(state='normal')
        self.scrolled_text.insert(tk.END, msg + '\n', record.levelname)
        self.scrolled_text.configure(state='disabled')
        self.scrolled_text.yview(tk.END)


class CheckDataWorker(threading.Thread):
    def __init__(self, filepaths=None, **kwargs):
        super().__init__()
        self._stop_event = threading.Event()
        self.filepaths = filepaths.copy()
        self.params = kwargs

    def run(self):
        if not self.filepaths:
            logger.warning("No data files selected")
            return

        logger.debug("Start data checking ...")
        while not self._stop_event.is_set() and self.filepaths:
            filepath = Path(self.filepaths.pop(0)).expanduser()
            logger.debug("Checking {} ...".format(filepath.name))

            d = read_data(filepath)
            try:
                errors = check_data(d, **self.params)
            except TypeError:
                msg = "Skip {} which is not a MoniSen data file.".format(filepath.name)
                logger.warning(msg)
            else:
                if errors:
                    outdir = filepath.parent
                    outpath = outdir.joinpath("確認事項{}.xlsx".format(filepath.stem))
                    if d.data_type == "tree":
                        header = ["plotid", "tag_no", "エラー対象", "エラー内容"]
                    else:
                        header = ["plotid", "s_date1", "trap_id", "エラー内容"]
                    save_errors_to_xlsx(errors, outpath, header)
                    logger.info("{} is created.".format(outpath.name))
                else:
                    logger.debug("No errors detected.")
            time.sleep(0.1)

        if self._stop_event.is_set():
            msg = "Data checking process has been stopped by the user."
            logger.warning(msg)
        else:
            logger.debug("Data checking finished.")

    def stop(self):
        self._stop_event.set()


class FileConvertWorker(threading.Thread):
    """
    Export a data file as a csv file.

    Parameters
    ----------
    filepath : str
        Path to a data file
    outdir : str, default None
        Output directory
    encoding : str, default "utf-8"
        Text encoding
    cleaning : bool, default True
        If clean up the data
    keep_comments : bool, default True
        If keep the comment lines

    """
    def __init__(self, filepaths=None, outdir: Optional[str] = None, **kwargs):
        super().__init__()
        self._stop_event = threading.Event()
        self.filepaths = filepaths.copy()
        self.outdir = outdir
        self.params = kwargs

    def run(self):
        if not self.filepaths:
            logger.warning("No data files selected")
            return

        # logger.debug("Start exporting ...")
        while not self._stop_event.is_set() and self.filepaths:
            filepath = Path(self.filepaths.pop(0)).expanduser()
            logger.debug("Exporting {} as csv ...".format(filepath.name))

            if self.outdir:
                outdir = Path(self.outdir)
                outdir.mkdir(parents=True, exist_ok=True)
            else:
                outdir = filepath.parent

            basename = filepath.stem
            outpath = outdir.joinpath(basename + ".csv")

            data = read_file(filepath)
            data_to_csv(data, outpath, **self.params)

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
        if not isinstance(parent, MainWindow):
            raise ValueError("parent is not MainWindow object")
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
    app = MainWindow(master=root)
    app.master.mainloop()


if __name__ == "__main__":
    main()
