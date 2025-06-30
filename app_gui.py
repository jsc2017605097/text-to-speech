import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QComboBox, QFileDialog, QSpinBox, QHBoxLayout
)
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QIcon
from convert import convert_text_file_to_speech


class ConvertThread(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(str)

    def __init__(self, input_file: str, voice: str, split_method: str, max_value: int):
        super().__init__()
        self.input_file = input_file
        self.voice = voice
        self.split_method = split_method
        self.max_value = max_value

    def run(self):
        def log_func(msg: str):
            self.log_signal.emit(msg)

        kwargs = {
            "input_file": self.input_file,
            "voice": self.voice,
            "split_method": self.split_method,
            "log_func": log_func
        }
        if self.split_method == "length":
            kwargs["max_length"] = self.max_value
        else:
            kwargs["max_sentences"] = self.max_value

        try:
            output_file = convert_text_file_to_speech(**kwargs)
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

        # Phương pháp chia
        layout.addWidget(QLabel("🔧 Cách chia văn bản:"))
        self.split_selector = QComboBox()
        self.split_selector.addItems([
            "Theo độ dài ký tự",
            "Theo số câu"
        ])
        self.split_selector.currentIndexChanged.connect(self.update_limit_label)
        layout.addWidget(self.split_selector)

        # Tham số tối đa
        self.limit_label = QLabel("Độ dài tối đa mỗi phần:")
        layout.addWidget(self.limit_label)
        self.limit_input = QSpinBox()
        self.limit_input.setRange(100, 10000)
        self.limit_input.setValue(5000)
        layout.addWidget(self.limit_input)

        # Nút bắt đầu
        self.btn_start = QPushButton("🚀 Bắt đầu chuyển đổi")
        self.btn_start.clicked.connect(self.start_convert)
        layout.addWidget(self.btn_start)

        # Log
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        layout.addWidget(self.log_output)

        self.setLayout(layout)

    def browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Chọn file .txt", "", "Text Files (*.txt)")
        if file_path:
            self.file_input.setText(file_path)

    def update_limit_label(self):
        if self.split_selector.currentIndex() == 0:
            self.limit_label.setText("Độ dài tối đa mỗi phần:")
            self.limit_input.setValue(5000)
        else:
            self.limit_label.setText("Số câu tối đa mỗi phần:")
            self.limit_input.setValue(50)

    def start_convert(self):
        input_file = self.file_input.text().strip()
        if not input_file or not os.path.exists(input_file):
            self.append_log("❌ Vui lòng chọn file .txt hợp lệ.")
            return

        voice = self.voice_selector.currentText().split(" - ")[1]
        split_method = "length" if self.split_selector.currentIndex() == 0 else "sentences"
        max_value = self.limit_input.value()

        self.append_log("🔄 Bắt đầu chuyển đổi...")
        self.btn_start.setEnabled(False)

        self.thread = ConvertThread(input_file, voice, split_method, max_value)
        self.thread.log_signal.connect(self.append_log)
        self.thread.finished_signal.connect(self.convert_finished)
        self.thread.start()

    def append_log(self, msg: str):
        self.log_output.append(msg)

    def convert_finished(self, output_path: str):
        self.append_log(f"\n✅ Đã tạo file audio: {output_path}")
        self.btn_start.setEnabled(True)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
