import sys
from pathlib import Path

from PySide2.QtCore import QMutex, QMutexLocker, QThread, Signal, Slot, QDir
from PySide2.QtWidgets import (QAction, QApplication, QFileDialog, QHBoxLayout,
                               QMainWindow, QMenu, QProgressBar, QPushButton, QTextEdit,
                               QVBoxLayout, QWidget)

from .datacheck import Moni1000Data, save_errors_to_xlsx
from .tree_data_transform import tree_data_transform
from .utils import file_to_csv


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)

        self.setupUI()
        self.pbvalue = 0
        self.path_to_files = []
        self.dir = Path("~").expanduser()

        self.worker = Worker()
        self.worker.fileStart.connect(self.printProcessing)
        self.worker.fileFinish.connect(self.updateProgress)
        self.worker.finished.connect(self.finishProcess)

    def setupUI(self):
        self.title = "moni1000utils"
        self.setWindowTitle(self.title)
        self.setGeometry(100, 100, 480, 400)

        centralWidget = QWidget()
        self.setCentralWidget(centralWidget)

        # ファイル選択ボタン
        self.fileSelectBtn = QPushButton("Select Data Files")
        self.fileSelectBtn.clicked.connect(self.onClickFileSelect)

        # データチェックボタン
        self.dataCheckBtn = QPushButton("Check Data")
        self.dataCheckBtn.setEnabled(False)
        self.dataCheckBtn.clicked.connect(self.onClickDataCheck)

        # CSV変換ボタン
        self.fileConvertBtn = QPushButton("Convert to CSV")
        self.fileConvertBtn.setEnabled(False)
        self.fileConvertBtn.clicked.connect(self.onClickFileConvert)

        # 終了ボタン
        self.exitBtn = QPushButton("Exit")
        self.exitBtn.setVisible(False)
        self.exitBtn.setEnabled(False)
        self.exitBtn.clicked.connect(self.close)

        # ログ出力
        self.textEdit = QTextEdit()
        self.textEdit.setReadOnly(True)

        # プログレスバー
        self.progressBar = QProgressBar()

        # レイアウト
        layoutH1 = QHBoxLayout()
        layoutH1.addWidget(self.fileSelectBtn)
        layoutH1.addWidget(self.dataCheckBtn)
        layoutH1.addWidget(self.fileConvertBtn)
        layoutH2 = QHBoxLayout()
        layoutH2.addWidget(self.exitBtn)

        layoutV = QVBoxLayout(centralWidget)
        layoutV.addLayout(layoutH1)
        layoutV.addWidget(self.textEdit)
        layoutV.addWidget(self.progressBar)
        layoutV.addLayout(layoutH2)

        # メニューバー
        fileSelectAction = QAction("ファイルを開く...(&X)", self)
        fileSelectAction.setShortcut("Ctrl+O")
        fileSelectAction.triggered.connect(self.onClickFileSelect)

        exitAction = QAction("終了(&X)", self)
        exitAction.setShortcut("Ctrl+Q")
        exitAction.triggered.connect(self.close)

        fileMenu = QMenu("moni1000utils(&F)")
        fileMenu.addAction(fileSelectAction)
        fileMenu.addAction(exitAction)
        self.menuBar().addMenu(fileMenu)

    def printLogTxt(self, log_string, color=None):
        self.textEdit.VLine
        if color:
            self.textEdit.setTextColor(color)
        self.textEdit.append(log_string)

    def onClickFileSelect(self):
        path_selected, _ = QFileDialog.getOpenFileNames(
            parent=self,
            caption="Select Files",
            dir=str(self.dir),
            filter="Data Files (*.xlsx *.xls *.csv)",
        )

        if self.path_to_files:
            self.path_to_files = []
            self.printLogTxt("---")

        if path_selected:
            for path in path_selected:
                self.path_to_files.append(path)
                parentdir = Path(path).parent
                if str(parentdir) != str(self.dir):
                    self.dir = parentdir

        if self.path_to_files:
            nfile = len(self.path_to_files)
            if nfile == 1:
                msg = "{} file selected".format(nfile)
            else:
                msg = "{} files selected".format(nfile)
            self.printLogTxt(msg)

            for path in self.path_to_files:
                self.printLogTxt(Path(path).name)

            self.dataCheckBtn.setEnabled(True)
            self.fileConvertBtn.setEnabled(True)

    def onClickDataCheck(self):
        self.exitBtn.setEnabled(False)
        self.printLogTxt("-----")
        self.printLogTxt("Start checking data...")
        self.setPrgressbar()
        self.worker.setup(self.path_to_files, mode="data_check")
        if not self.worker.isRunning():
            self.worker.restart()
        self.worker.start()
        self.resetPrgressbar()

    def onClickFileConvert(self):
        self.exitBtn.setEnabled(False)
        self.printLogTxt("-----")
        self.printLogTxt("Start converting EXCEL files to CSV...")
        self.setPrgressbar()
        self.worker.setup(self.path_to_files, mode="file_convert")
        if not self.worker.isRunning():
            self.worker.restart()
        self.worker.start()
        self.resetPrgressbar()

    def setPrgressbar(self):
        self.progressBar.setValue(0)
        self.progressBar.setMinimum(0)
        self.progressBar.setMaximum(len(self.path_to_files))

    def resetPrgressbar(self):
        self.pbvalue = 0
        self.progressBar.setValue(self.pbvalue)

    @Slot(str)
    def printProcessing(self, sig):
        self.printLogTxt("Processing {}...".format(Path(sig).name))

    @Slot(str)
    def updateProgress(self, sig):
        self.printLogTxt(sig)
        self.pbvalue += 1
        self.progressBar.setValue(self.pbvalue)

    @Slot(str)
    def finishProcess(self):
        self.worker.wait()
        self.exitBtn.setEnabled(True)
        self.exitBtn.setVisible(True)


class Worker(QThread):

    fileStart = Signal(str)
    fileFinish = Signal(str)

    def __init__(self):
        QThread.__init__(self)
        self.stopped = False
        self.mutex = QMutex()

    def setup(self, path_to_files, mode):
        self.path_to_files = path_to_files
        self.mode = mode
        self.stopped = False

    def stop(self):
        with QMutexLocker(self.mutex):
            self.stopped = True

    def restart(self):
        with QMutexLocker(self.mutex):
            self.stopped = True

    def run(self):
        for filepath in self.path_to_files:
            # 処理開始シグナル
            self.fileStart.emit(filepath)

            if self.mode == "data_check":
                # データチェック
                msg = self.data_check(filepath)
            else:
                # CSV変換
                if Path(filepath).suffix == ".csv":
                    msg = "Skipped."
                else:
                    self.file_convert(filepath)
                    msg = "Done."

            # 処理完了シグナル
            self.fileFinish.emit(msg)

        # プロセス終了シグナル
        self.finished.emit()
        self.stop()

    def data_check(self, filepath):
        filepath = Path(filepath)
        mdf = Moni1000Data.from_file(filepath)
        if mdf.data_type == "other":
            msg = "File is not Moni1000 data"
            return msg

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

        return msg

    def file_convert(self, filepath):
        filepath = Path(filepath)
        mdf = Moni1000Data.from_file(filepath)

        if mdf.data_type == "tree":
            tree_data_transform(filepath)
            file_to_csv(filepath)
        else:
            file_to_csv(filepath)


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
