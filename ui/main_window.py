"""主窗口。

布局:
  ┌──────────────────────────────────────────────┐
  │ 工具栏: 数据源选择 / 暂停 / 继续 / 清空 / DB │
  ├───────────────────────┬──────────────────────┤
  │                       │                      │
  │   船舶信息表格         │    经纬度方格图      │
  │   (左侧)              │    (右侧)            │
  │                       │                      │
  ├───────────────────────┴──────────────────────┤
  │ 状态栏: 收包 / BCC / 解码 / 当前数据源       │
  └──────────────────────────────────────────────┘
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QToolBar, QStatusBar, QFileDialog, QMessageBox,
    QComboBox, QLabel,
)

from config import CONFIG, PROJECT_ROOT, DATA_DIR
from link.data_source import DataSource, make_source
from link.raw_logger import RawLogger, ResultLogger
from ais.ais_ship import AIS_Ship

from .controller import Controller, Stats
from .grid_canvas import GridCanvas
from .ship_table import ShipTable


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("船舶AIS信息解析系统")
        self.resize(CONFIG.ui.window_width, CONFIG.ui.window_height)

        # 核心组件
        self.controller = Controller(self)
        self.table = ShipTable(max_rows=CONFIG.ui.table_max_rows, parent=self)
        self.canvas = GridCanvas(
            grid_size=CONFIG.ui.grid_size,
            grid_step_deg=CONFIG.ui.grid_step_deg,
            parent=self,
        )

        # 数据源(初始 None)
        self.source: DataSource | None = None

        # 日志
        self.raw_log = RawLogger(DATA_DIR / "raw_log.txt", parent=self)
        self.result_log = ResultLogger(DATA_DIR / "parsed_log.txt", parent=self)

        # 数据库(可选用)
        self.db_store = None
        if CONFIG.db.backend == "sqlite":
            from storage.sqlite_store import SqliteStore
            self.db_store = SqliteStore(CONFIG.db.sqlite_path, parent=self)
        elif CONFIG.db.backend == "mysql":
            try:
                from storage.mysql_store import MysqlStore
                cfg = CONFIG.db
                self.db_store = MysqlStore(
                    host=cfg.mysql_host, port=cfg.mysql_port,
                    user=cfg.mysql_user, password=cfg.mysql_password,
                    database=cfg.mysql_database, parent=self,
                )
            except Exception as e:
                QMessageBox.warning(self, "MySQL", f"无法连接 MySQL: {e}\n将退化为无数据库模式")

        self._build_ui()
        self._wire()

    # ---- UI 构建 ----
    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.canvas, 1)

        # 工具栏
        tb = QToolBar("主工具栏")
        tb.setMovable(False)
        self.addToolBar(tb)

        self.src_combo = QComboBox()
        self.src_combo.addItems(["文件回放", "串口", "网口"])
        tb.addWidget(QLabel("数据源: "))
        tb.addWidget(self.src_combo)

        self.act_open = QAction("打开文件...", self)
        tb.addAction(self.act_open)

        self.act_start = QAction("开始", self)
        tb.addAction(self.act_start)

        self.act_pause = QAction("暂停", self)
        tb.addAction(self.act_pause)

        self.act_resume = QAction("继续", self)
        tb.addAction(self.act_resume)

        self.act_clear = QAction("清空", self)
        tb.addAction(self.act_clear)

        # 状态栏
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.lbl_stats = QLabel("收包: 0 | BCC: 0/- | 解码: 0")
        self.lbl_source = QLabel("源: -")
        self.status.addWidget(self.lbl_stats)
        self.status.addPermanentWidget(self.lbl_source)

    # ---- 信号槽 ----
    def _wire(self) -> None:
        self.act_open.triggered.connect(self._on_open_file)
        self.act_start.triggered.connect(self._on_start)
        self.act_pause.triggered.connect(self._on_pause)
        self.act_resume.triggered.connect(self._on_resume)
        self.act_clear.triggered.connect(self._on_clear)

        self.controller.ship_received.connect(self._on_ship)
        self.controller.stats_changed.connect(self._on_stats)
        self.controller.error.connect(lambda e: self.status.showMessage(e, 5000))

    # ---- 数据源切换 ----
    def _stop_source(self) -> None:
        if self.source is not None:
            try:
                self.source.stop()
            except Exception:
                pass
            self.source = None

    def start_file_source(self, path: str) -> None:
        self._stop_source()
        self.source = make_source("file", path=path)
        self._connect_source()
        self.source.start()

    def start_serial_source(self, port: str, baud: int) -> None:
        self._stop_source()
        self.source = make_source("serial", port=port, baudrate=baud)
        self._connect_source()
        self.source.start()

    def start_network_source(self, host: str, port: int) -> None:
        self._stop_source()
        self.source = make_source("net", host=host, port=port)
        self._connect_source()
        self.source.start()

    def _connect_source(self) -> None:
        if self.source is None:
            return
        self.source.lines.connect(self.raw_log.write)
        self.source.lines.connect(self.controller.on_line)
        self.source.status.connect(lambda s: self.lbl_source.setText(f"源: {s}"))
        self.source.error.connect(lambda e: self.status.showMessage(f"[ERR] {e}", 5000))
        self.lbl_source.setText(f"源: {self.source.name}")

    # ---- 槽 ----
    def _on_open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 NMEA 样本", str(PROJECT_ROOT / "tests" / "samples"),
            "文本文件 (*.txt);;所有文件 (*)",
        )
        if path:
            self.start_file_source(path)

    def _on_start(self) -> None:
        kind_idx = self.src_combo.currentIndex()
        if kind_idx == 0:
            # 文件
            default = str(PROJECT_ROOT / "tests" / "samples" / "sample_nmea.txt")
            self.start_file_source(default)
        elif kind_idx == 1:
            self.start_serial_source(CONFIG.serial.port, CONFIG.serial.baudrate)
        else:
            self.start_network_source(CONFIG.network.host, CONFIG.network.port)

    def _on_pause(self) -> None:
        self.controller.pause()
        self.status.showMessage("已暂停", 3000)

    def _on_resume(self) -> None:
        self.controller.resume()
        self.status.showMessage("已继续", 3000)

    def _on_clear(self) -> None:
        self.controller.reset()
        self.table.clear_all()
        self.canvas.reset()
        self.status.showMessage("已清空", 3000)

    @Slot(object)
    def _on_ship(self, ship: AIS_Ship) -> None:
        self.table.on_ship(ship)
        self.canvas.on_ship(ship)
        self.result_log.write(ship)
        if self.db_store is not None:
            try:
                self.db_store.insert(ship)
            except Exception as e:
                self.status.showMessage(f"DB 写入失败: {e}", 3000)

    @Slot(object)
    def _on_stats(self, stats: Stats) -> None:
        text = (f"收包: {stats.rx} | BCC: {stats.bcc_pass}/{stats.bcc_fail} "
                f"| 解码: {stats.decoded} | 类型分布: {stats.by_type}")
        self.lbl_stats.setText(text)

    def closeEvent(self, event) -> None:  # noqa: N802
        self._stop_source()
        self.raw_log.close()
        self.result_log.close()
        if self.db_store is not None:
            self.db_store.close()
        super().closeEvent(event)