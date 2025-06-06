import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QTextEdit, QHBoxLayout
)
from PyQt5.QtCore import QThread, pyqtSignal
from convert import run_convert
from PyQt5.QtGui import QIcon

class ConvertThread(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(str)

    def __init__(self, topic, api_key, num_parts):
        super().__init__()
        self.topic = topic
        self.api_key = api_key
        self.num_parts = num_parts

    def run(self):
        def log_func(msg):
            self.log_signal.emit(msg)

        try:
            final_audio = run_convert(self.topic, self.api_key, self.num_parts, log_func=log_func)
            self.log_signal.emit("✅ Hoàn tất chuyển đổi!")
            self.finished_signal.emit(final_audio)
        except Exception as e:
            self.log_signal.emit(f"❌ Lỗi: {e}")

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dâu Tây Audio")
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.abspath(".")

        icon_path = os.path.join(base_path, "dautay.ico")
        self.setWindowIcon(QIcon(icon_path))
        self.resize(600, 450)

        layout = QVBoxLayout()

        # Chủ đề
        layout.addWidget(QLabel("Nhập chủ đề:"))
        self.topic_input = QLineEdit()
        layout.addWidget(self.topic_input)

        # API Key
        layout.addWidget(QLabel("Nhập OpenRouter API Key:"))
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.Password)  # ẩn key khi nhập
        layout.addWidget(self.api_key_input)

        # Số phần câu chuyện
        layout.addWidget(QLabel("Số phần câu chuyện:"))
        self.num_parts_input = QLineEdit()
        self.num_parts_input.setText("12")  # mặc định 12 phần
        layout.addWidget(self.num_parts_input)

        # Nút bắt đầu và mở file
        self.btn_start = QPushButton("Bắt đầu chuyển đổi")
        layout.addWidget(self.btn_start)

        self.btn_open = QPushButton("Mở thư mục chứa file audio cuối")
        self.btn_open.setEnabled(False)
        layout.addWidget(self.btn_open)

        # Log
        layout.addWidget(QLabel("Log:"))
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        layout.addWidget(self.log_output)

        self.setLayout(layout)

        # Kết nối nút
        self.btn_start.clicked.connect(self.start_convert)
        self.btn_open.clicked.connect(self.open_audio_file)

        self.final_audio_file = None
        self.thread = None

    def start_convert(self):
        topic = self.topic_input.text().strip()
        api_key = self.api_key_input.text().strip()
        num_parts_str = self.num_parts_input.text().strip()

        if not topic:
            self.log_output.append("⚠️ Vui lòng nhập chủ đề!")
            return
        if not api_key:
            self.log_output.append("⚠️ Vui lòng nhập API Key!")
            return
        if not num_parts_str.isdigit() or int(num_parts_str) < 1:
            self.log_output.append("⚠️ Số phần phải là số nguyên dương!")
            return

        num_parts = int(num_parts_str)

        self.log_output.clear()
        self.btn_start.setEnabled(False)
        self.btn_open.setEnabled(False)

        self.thread = ConvertThread(topic, api_key, num_parts)
        self.thread.log_signal.connect(self.append_log)
        self.thread.finished_signal.connect(self.convert_finished)
        self.thread.start()

    def append_log(self, message):
        self.log_output.append(message)

    def convert_finished(self, audio_path):
        self.final_audio_file = audio_path
        self.btn_start.setEnabled(True)
        self.btn_open.setEnabled(True)
        self.log_output.append(f"🎉 File audio cuối: {audio_path}")

    def open_audio_file(self):
        if self.final_audio_file and os.path.exists(self.final_audio_file):
            folder = os.path.dirname(self.final_audio_file)
            if sys.platform.startswith('win'):
                os.startfile(folder)
            elif sys.platform == 'darwin':
                os.system(f'open "{folder}"')
            else:
                os.system(f'xdg-open "{folder}"')
        else:
            self.log_output.append("⚠️ File audio không tồn tại hoặc không thể mở.")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
