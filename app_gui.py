import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QFileDialog, QSlider, QHBoxLayout,
    QComboBox
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtGui import QIcon
from convert import run_convert
from make_video_from_loop import make_video_loop_with_ffmpeg

class ConvertThread(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(str)

    def __init__(self, topic, api_key, num_parts, video_path=None, music_path=None, music_volume=30, voice="vi-VN-HoaiMyNeural"):
        super().__init__()
        self.topic = topic
        self.api_key = api_key
        self.num_parts = num_parts
        self.video_path = video_path
        self.music_path = music_path
        self.music_volume = music_volume
        self.voice = voice

    def run(self):
        def log_func(msg):
            self.log_signal.emit(msg)

        try:
            final_audio = run_convert(self.topic, self.api_key, self.num_parts, log_func=log_func, voice=self.voice)
            self.log_signal.emit("✅ Hoàn tất chuyển đổi âm thanh!")

            if self.video_path and os.path.exists(self.video_path):
                video_output = final_audio.replace(".mp3", ".mp4")
                log_func("🎞️ Đang ghép với video mẫu và nhạc nền...")
                make_video_loop_with_ffmpeg(
                    self.video_path, final_audio, video_output,
                    log_func=log_func,
                    music_path=self.music_path,
                    music_volume=self.music_volume
                )
                self.finished_signal.emit(video_output)
            else:
                self.log_signal.emit("⚠️ Không có video mẫu, chỉ tạo audio.")
                self.finished_signal.emit(final_audio)

        except Exception as e:
            self.log_signal.emit(f"❌ Lỗi: {e}")

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dâu Tây Video Maker")
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.abspath(".")

        icon_path = os.path.join(base_path, "dautay.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.resize(640, 600)

        layout = QVBoxLayout()

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

        # Giọng đọc
        layout.addWidget(QLabel("🎤 Chọn giọng đọc:"))
        self.voice_selector = QComboBox()
        self.voice_selector.addItems([
            "Nữ - vi-VN-HoaiMyNeural",
            "Nam - vi-VN-NamMinhNeural"
        ])
        layout.addWidget(self.voice_selector)

        # Video mẫu
        layout.addWidget(QLabel("📼 Chọn video mẫu:"))
        self.video_path_label = QLabel("(Chưa chọn)")
        layout.addWidget(self.video_path_label)
        self.btn_browse_video = QPushButton("Chọn video...")
        self.btn_browse_video.clicked.connect(self.browse_video)
        layout.addWidget(self.btn_browse_video)

        # Nhạc nền
        layout.addWidget(QLabel("🎵 Chọn nhạc nền (tùy chọn):"))
        self.music_path_label = QLabel("(Chưa chọn)")
        layout.addWidget(self.music_path_label)
        self.btn_browse_music = QPushButton("Chọn nhạc nền...")
        self.btn_browse_music.clicked.connect(self.browse_music)
        layout.addWidget(self.btn_browse_music)

        # Âm lượng
        layout.addWidget(QLabel("🔊 Âm lượng nhạc nền (%):"))
        volume_layout = QHBoxLayout()
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(30)
        self.volume_slider.valueChanged.connect(self.update_volume_label)

        self.volume_label = QLabel("30%")
        volume_layout.addWidget(self.volume_slider)
        volume_layout.addWidget(self.volume_label)
        layout.addLayout(volume_layout)

        self.btn_start = QPushButton("🚀 Tạo Video")
        self.btn_start.clicked.connect(self.start_convert)
        layout.addWidget(self.btn_start)

        self.btn_open = QPushButton("📂 Mở thư mục kết quả")
        self.btn_open.setEnabled(False)
        self.btn_open.clicked.connect(self.open_output_folder)
        layout.addWidget(self.btn_open)

        layout.addWidget(QLabel("📋 Log:"))
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        layout.addWidget(self.log_output)

        self.setLayout(layout)

        self.selected_video_path = None
        self.selected_music_path = None
        self.final_output_file = None

    def update_volume_label(self):
        self.volume_label.setText(f"{self.volume_slider.value()}%")

    def browse_video(self):
        path, _ = QFileDialog.getOpenFileName(self, "Chọn video nền", "", "Video Files (*.mp4 *.mov *.avi)")
        if path:
            self.selected_video_path = path
            self.video_path_label.setText(os.path.basename(path))

    def browse_music(self):
        path, _ = QFileDialog.getOpenFileName(self, "Chọn nhạc nền", "", "Audio Files (*.mp3 *.wav)")
        if path:
            self.selected_music_path = path
            self.music_path_label.setText(os.path.basename(path))

    def start_convert(self):
        topic = self.topic_input.text().strip()
        api_key = self.api_key_input.text().strip()
        num_parts_str = self.num_parts_input.text().strip()

        if not topic:
            self.append_log("⚠️ Vui lòng nhập chủ đề!")
            return
        if not api_key:
            self.append_log("⚠️ Vui lòng nhập API Key!")
            return
        if not num_parts_str.isdigit() or int(num_parts_str) < 1:
            self.append_log("⚠️ Số phần không hợp lệ!")
            return
        if not self.selected_video_path:
            self.append_log("⚠️ Vui lòng chọn video mẫu!")
            return

        num_parts = int(num_parts_str)
        music_volume = self.volume_slider.value()
        voice_text = self.voice_selector.currentText()
        voice = voice_text.split(" - ")[1].strip()

        self.log_output.clear()
        self.btn_start.setEnabled(False)
        self.btn_open.setEnabled(False)

        self.thread = ConvertThread(
            topic, api_key, num_parts,
            video_path=self.selected_video_path,
            music_path=self.selected_music_path,
            music_volume=music_volume,
            voice=voice
        )
        self.thread.log_signal.connect(self.append_log)
        self.thread.finished_signal.connect(self.convert_finished)
        self.thread.start()

    def append_log(self, msg):
        self.log_output.append(msg)

    def convert_finished(self, output_file):
        self.final_output_file = output_file
        self.btn_start.setEnabled(True)
        self.btn_open.setEnabled(True)
        self.append_log(f"✅ Đã tạo video: {output_file}")

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
