import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QComboBox, QProgressBar
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtGui import QIcon
from convert import run_convert


class ConvertThread(QThread):
    """Thread chỉ tạo AUDIO (mp3) từ chủ đề – KHÔNG xử lý video"""

    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(str)

    def __init__(self, topic: str, api_key: str, num_parts: int, voice: str) -> None:
        super().__init__()
        self.topic = topic
        self.api_key = api_key
        self.num_parts = num_parts
        self.voice = voice

    def run(self):
        def log_func(msg: str):
            self.log_signal.emit(msg)

        try:
            final_audio = run_convert(
                self.topic,
                self.api_key,
                self.num_parts,
                log_func=log_func,
                voice=self.voice,
            )
            self.log_signal.emit("✅ Hoàn tất tạo audio!")
            self.finished_signal.emit(final_audio)
        except Exception as e:
            self.log_signal.emit(f"❌ Lỗi: {e}")


class MainWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Dâu Tây Audio Maker")

        # Icon khi đóng gói PyInstaller (tuỳ chọn)
        base_path = sys._MEIPASS if getattr(sys, "frozen", False) else os.path.abspath(".")
        icon_path = os.path.join(base_path, "dautay.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.resize(500, 500)
        layout = QVBoxLayout()

        # ---------- Thông tin tạo audio ----------
        layout.addWidget(QLabel("🎯 Chủ đề:"))
        self.topic_input = QLineEdit()
        layout.addWidget(self.topic_input)

        layout.addWidget(QLabel("🔑 API Key:"))
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.api_key_input)

        layout.addWidget(QLabel("📑 Số phần câu chuyện:"))
        self.num_parts_input = QLineEdit("10")
        layout.addWidget(self.num_parts_input)

        layout.addWidget(QLabel("🎤 Chọn giọng đọc:"))
        self.voice_selector = QComboBox()
        self.voice_selector.addItems(
            [
                "Nữ - vi-VN-HoaiMyNeural",
                "Nam - vi-VN-NamMinhNeural",
            ]
        )
        layout.addWidget(self.voice_selector)

        # ---------- Progress & log ----------
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        layout.addWidget(self.log_output)

        # ---------- Nút action ----------
        self.btn_start = QPushButton("🚀 Tạo Audio")
        self.btn_start.clicked.connect(self.start_convert)
        layout.addWidget(self.btn_start)

        self.btn_open = QPushButton("📂 Mở thư mục kết quả")
        self.btn_open.setEnabled(False)
        self.btn_open.clicked.connect(self.open_output_folder)
        layout.addWidget(self.btn_open)

        self.setLayout(layout)

        # ---------- State ----------
        self.final_output_file: str | None = None

    # --------------------------------------------------
    # Core workflow
    # --------------------------------------------------

    def start_convert(self):
        self.log_output.clear()
        self.progress_bar.setValue(0)
        self.btn_start.setEnabled(False)
        self.btn_open.setEnabled(False)

        # Validate input
        topic = self.topic_input.text().strip()
        api_key = self.api_key_input.text().strip()
        num_parts_str = self.num_parts_input.text().strip()

        if not topic:
            self.append_log("⚠️ Vui lòng nhập chủ đề!")
            self.btn_start.setEnabled(True)
            return
        if not api_key:
            self.append_log("⚠️ Vui lòng nhập API Key!")
            self.btn_start.setEnabled(True)
            return
        if not num_parts_str.isdigit() or int(num_parts_str) < 1:
            self.append_log("⚠️ Số phần không hợp lệ!")
            self.btn_start.setEnabled(True)
            return

        num_parts = int(num_parts_str)
        voice = self.voice_selector.currentText().split(" - ")[1].strip()

        self.thread = ConvertThread(topic, api_key, num_parts, voice)
        self.thread.log_signal.connect(self.handle_log_signal)
        self.thread.finished_signal.connect(self.convert_finished)
        self.thread.start()

    # --------------------------------------------------
    # Slots for thread signals
    # --------------------------------------------------

    def handle_log_signal(self, msg: str):
        """Log + cập nhật progress nếu msg trả về dạng ⏳ Render: xx%"""
        if msg.startswith("⏳ Render:"):
            try:
                percent_str = msg.split("⏳ Render:")[1].strip().replace("%", "")
                self.progress_bar.setValue(int(float(percent_str)))
            except Exception:
                self.log_output.append(msg)
        else:
            self.log_output.append(msg)

    def convert_finished(self, output_file: str):
        self.final_output_file = output_file
        self.append_log(f"✅ Đã tạo audio: {output_file}")
        self.progress_bar.setValue(100)
        self.btn_open.setEnabled(True)
        self.btn_start.setEnabled(True)

    # --------------------------------------------------
    # Misc helpers
    # --------------------------------------------------

    def append_log(self, msg: str):
        self.log_output.append(msg)

    def open_output_folder(self):
        if self.final_output_file and os.path.exists(self.final_output_file):
            folder = os.path.dirname(self.final_output_file)
            if sys.platform.startswith("win"):
                os.startfile(folder)
            elif sys.platform == "darwin":
                os.system(f"open '{folder}'")
            else:
                os.system(f"xdg-open '{folder}'")
        else:
            self.append_log("⚠️ Không tìm thấy file.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
