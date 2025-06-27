import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QComboBox, QProgressBar, QCheckBox
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtGui import QIcon
from convert import run_convert
from subtitle_generator import generate_subtitle


class ConvertThread(QThread):
    """Thread tạo AUDIO (mp3) từ chủ đề và có thể tạo phụ đề"""

    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(str)

    def __init__(self, topic: str, api_key: str, num_parts: int, voice: str, create_subtitle: bool, whisper_model: str, channel_name: str) -> None:
        super().__init__()
        self.topic = topic
        self.api_key = api_key
        self.num_parts = num_parts
        self.voice = voice
        self.create_subtitle = create_subtitle
        self.whisper_model = whisper_model
        self.channel_name = channel_name

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
                channel_name=self.channel_name
            )
            self.log_signal.emit("✅ Hoàn tất tạo audio!")
            
            # Tạo phụ đề nếu được chọn
            if self.create_subtitle:
                self.log_signal.emit("🎬 Đang tạo phụ đề...")
                try:
                    subtitle_file = generate_subtitle(final_audio, self.whisper_model, log_func)
                    self.log_signal.emit(f"✅ Đã tạo phụ đề: {subtitle_file}")
                except Exception as e:
                    self.log_signal.emit(f"❌ Lỗi tạo phụ đề: {e}")
                    
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

        self.resize(500, 600)
        layout = QVBoxLayout()

        # ---------- Tên kênh ----------
        layout.addWidget(QLabel("📺 Tên kênh:"))
        self.channel_name_input = QLineEdit("Pháp Âm Bình An")
        layout.addWidget(self.channel_name_input)

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

        # ---------- Tùy chọn tạo phụ đề ----------
        self.subtitle_checkbox = QCheckBox("🎬 Tạo phụ đề (SRT file)")
        self.subtitle_checkbox.setChecked(False)
        self.subtitle_checkbox.toggled.connect(self.toggle_whisper_model)
        layout.addWidget(self.subtitle_checkbox)

        layout.addWidget(QLabel("🤖 Whisper Model:"))
        self.whisper_model_selector = QComboBox()
        self.whisper_model_selector.addItems([
            "tiny - Nhanh nhất, chất lượng thấp (~39MB)",
            "base - Cân bằng tốc độ và chất lượng (~74MB)", 
            "small - Chất lượng tốt (~244MB)",
            "medium - Chất lượng cao (~769MB)",
            "large - Chất lượng tốt nhất (~1550MB)"
        ])
        self.whisper_model_selector.setCurrentIndex(1)  # Default: base
        self.whisper_model_selector.setEnabled(False)  # Disable ban đầu
        layout.addWidget(self.whisper_model_selector)

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

    def start_convert(self):
        self.log_output.clear()
        self.progress_bar.setValue(0)
        self.btn_start.setEnabled(False)
        self.btn_open.setEnabled(False)

        # Validate input
        channel_name = self.channel_name_input.text().strip()
        topic = self.topic_input.text().strip()
        api_key = self.api_key_input.text().strip()
        num_parts_str = self.num_parts_input.text().strip()

        if not channel_name:
            self.append_log("⚠️ Vui lòng nhập tên kênh!")
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
        create_subtitle = self.subtitle_checkbox.isChecked()
        whisper_model = self.whisper_model_selector.currentText().split(" - ")[0].strip()

        self.thread = ConvertThread(topic, api_key, num_parts, voice, create_subtitle, whisper_model, channel_name)
        self.thread.log_signal.connect(self.handle_log_signal)
        self.thread.finished_signal.connect(self.convert_finished)
        self.thread.start()

    def toggle_whisper_model(self, checked: bool):
        """Bật/tắt dropdown model khi checkbox được chọn/bỏ chọn"""
        self.whisper_model_selector.setEnabled(checked)

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