import sys
import os
import subprocess
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QComboBox, QFileDialog, QHBoxLayout
)
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QIcon
from convert import convert_text_file_to_speech


class ConvertThread(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(str)

    def __init__(self, input_file: str, voice: str):
        super().__init__()
        self.input_file = input_file
        self.voice = voice

    def run(self):
        def log_func(msg: str):
            self.log_signal.emit(msg)

        try:
            output_file = convert_text_file_to_speech(
                input_file=self.input_file,
                voice=self.voice,
                log_func=log_func
            )
            if output_file:
                self.finished_signal.emit(output_file)
            else:
                self.log_signal.emit("❌ Chuyển đổi thất bại.")
        except Exception as e:
            self.log_signal.emit(f"❌ Lỗi: {e}")


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Text to Speech")

        base_path = sys._MEIPASS if getattr(sys, "frozen", False) else os.path.abspath(".")
        icon_path = os.path.join(base_path, "tts.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.resize(500, 500)
        layout = QVBoxLayout()

        # Chọn file
        layout.addWidget(QLabel("📄 File .txt đầu vào:"))
        file_layout = QHBoxLayout()
        self.file_input = QLineEdit()
        file_layout.addWidget(self.file_input)
        btn_browse = QPushButton("🔍 Chọn file")
        btn_browse.clicked.connect(self.browse_file)
        file_layout.addWidget(btn_browse)
        layout.addLayout(file_layout)

        # Chọn giọng
        layout.addWidget(QLabel("🎤 Giọng đọc:"))
        self.voice_selector = QComboBox()
        self.voice_selector.addItems([
            "Nam Minh - vi-VN-NamMinhNeural",
            "Hoài My - vi-VN-HoaiMyNeural",
            "Tuấn - vi-VN-TuanNeural",
            "Vy - vi-VN-VyNeural"
        ])
        layout.addWidget(self.voice_selector)

        # Nút bắt đầu
        self.btn_start = QPushButton("🚀 Bắt đầu chuyển đổi")
        self.btn_start.clicked.connect(self.start_convert)
        layout.addWidget(self.btn_start)

        # Log
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        layout.addWidget(self.log_output)

        # Nút mở thư mục
        self.btn_open_folder = QPushButton("📂 Mở thư mục chứa file audio")
        self.btn_open_folder.setEnabled(False)
        self.btn_open_folder.clicked.connect(self.open_output_folder)
        layout.addWidget(self.btn_open_folder)

        self.setLayout(layout)

    def browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Chọn file .txt", "", "Text Files (*.txt)")
        if file_path:
            self.file_input.setText(file_path)

    def start_convert(self):
        input_file = self.file_input.text().strip()
        if not input_file or not os.path.exists(input_file):
            self.append_log("❌ Vui lòng chọn file .txt hợp lệ.")
            return

        voice = self.voice_selector.currentText().split(" - ")[1]

        self.append_log("🔄 Bắt đầu chuyển đổi...")
        self.btn_start.setEnabled(False)
        self.btn_open_folder.setEnabled(False)

        self.thread = ConvertThread(input_file, voice)
        self.thread.log_signal.connect(self.append_log)
        self.thread.finished_signal.connect(self.convert_finished)
        self.thread.start()

    def append_log(self, msg: str):
        self.log_output.append(msg)

    def convert_finished(self, output_path: str):
        self.append_log(f"\n✅ Đã tạo file audio: {output_path}")
        self.btn_start.setEnabled(True)
        self.output_folder = os.path.dirname(output_path)
        self.btn_open_folder.setEnabled(True)

    def open_output_folder(self):
        if hasattr(self, "output_folder") and os.path.exists(self.output_folder):
            if sys.platform == "win32":
                os.startfile(self.output_folder)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", self.output_folder])
            else:
                subprocess.Popen(["xdg-open", self.output_folder])


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
