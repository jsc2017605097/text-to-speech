import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QFileDialog, QSlider, QHBoxLayout,
    QComboBox, QRadioButton, QProgressBar
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

class MergeThread(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(str)

    def __init__(self, video_path, audio_path, output_path, music_path=None, music_volume=30):
        super().__init__()
        self.video_path = video_path
        self.audio_path = audio_path
        self.output_path = output_path
        self.music_path = music_path
        self.music_volume = music_volume

    def run(self):
        def log_func(msg):
            self.log_signal.emit(msg)

        try:
            make_video_loop_with_ffmpeg(
                self.video_path,
                self.audio_path,
                self.output_path,
                log_func=log_func,
                music_path=self.music_path,
                music_volume=self.music_volume
            )
            self.finished_signal.emit(self.output_path)
        except Exception as e:
            self.log_signal.emit(f"❌ Lỗi khi tạo video: {e}")

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
        self.resize(640, 700)  # tăng chiều cao cho progress bar

        layout = QVBoxLayout()

        # --- Chọn audio mới hoặc có sẵn - ĐƯA LÊN ĐẦU ---
        layout.addWidget(QLabel("⚙️ Chọn cách tạo audio:"))
        radio_layout = QHBoxLayout()
        self.radio_create_audio = QRadioButton("Tạo audio mới")
        self.radio_use_audio = QRadioButton("Dùng file audio có sẵn")
        self.radio_create_audio.setChecked(True)
        radio_layout.addWidget(self.radio_create_audio)
        radio_layout.addWidget(self.radio_use_audio)
        layout.addLayout(radio_layout)

        # Kết nối radio thay đổi
        self.radio_create_audio.toggled.connect(self.toggle_audio_option)

        # --- Các widget cho "Audio mới" ---
        self.widget_audio_new = QWidget()
        layout_audio_new = QVBoxLayout()

        layout_audio_new.addWidget(QLabel("🎯 Chủ đề:"))
        self.topic_input = QLineEdit()
        layout_audio_new.addWidget(self.topic_input)

        layout_audio_new.addWidget(QLabel("🔑 API Key:"))
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.Password)
        layout_audio_new.addWidget(self.api_key_input)

        layout_audio_new.addWidget(QLabel("📑 Số phần câu chuyện:"))
        self.num_parts_input = QLineEdit("10")
        layout_audio_new.addWidget(self.num_parts_input)

        layout_audio_new.addWidget(QLabel("🎤 Chọn giọng đọc:"))
        self.voice_selector = QComboBox()
        self.voice_selector.addItems([
            "Nữ - vi-VN-HoaiMyNeural",
            "Nam - vi-VN-NamMinhNeural"
        ])
        layout_audio_new.addWidget(self.voice_selector)

        self.widget_audio_new.setLayout(layout_audio_new)
        layout.addWidget(self.widget_audio_new)

        # --- Các widget cho "Audio có sẵn" ---
        self.widget_audio_exist = QWidget()
        layout_audio_exist = QVBoxLayout()

        layout_audio_exist.addWidget(QLabel("🎧 Chọn file audio có sẵn:"))
        self.existing_audio_label = QLabel("(Chưa chọn)")
        layout_audio_exist.addWidget(self.existing_audio_label)
        self.btn_browse_audio = QPushButton("Chọn audio...")
        self.btn_browse_audio.clicked.connect(self.browse_existing_audio)
        layout_audio_exist.addWidget(self.btn_browse_audio)

        self.widget_audio_exist.setLayout(layout_audio_exist)
        layout.addWidget(self.widget_audio_exist)

        # --- Các widget chung khác ---
        layout.addWidget(QLabel("📼 Chọn video mẫu:"))
        self.video_path_label = QLabel("(Chưa chọn)")
        layout.addWidget(self.video_path_label)
        self.btn_browse_video = QPushButton("Chọn video...")
        self.btn_browse_video.clicked.connect(self.browse_video)
        layout.addWidget(self.btn_browse_video)

        layout.addWidget(QLabel("🎵 Chọn nhạc nền (tùy chọn):"))
        self.music_path_label = QLabel("(Chưa chọn)")
        layout.addWidget(self.music_path_label)
        self.btn_browse_music = QPushButton("Chọn nhạc nền...")
        self.btn_browse_music.clicked.connect(self.browse_music)
        layout.addWidget(self.btn_browse_music)

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

        # --- Progress bar hiển thị tiến trình render ---
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        # Log text
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        layout.addWidget(self.log_output)

        self.btn_start = QPushButton("🚀 Tạo Video")
        self.btn_start.clicked.connect(self.start_convert)
        layout.addWidget(self.btn_start)

        self.btn_open = QPushButton("📂 Mở thư mục kết quả")
        self.btn_open.setEnabled(False)
        self.btn_open.clicked.connect(self.open_output_folder)
        layout.addWidget(self.btn_open)

        self.setLayout(layout)

        # Giá trị khởi tạo
        self.selected_video_path = None
        self.selected_music_path = None
        self.selected_existing_audio = None
        self.final_output_file = None

        # Mặc định ẩn widget audio có sẵn (vì chọn tạo mới)
        self.toggle_audio_option()

    def toggle_audio_option(self):
        use_existing = self.radio_use_audio.isChecked()
        self.widget_audio_exist.setVisible(use_existing)
        self.widget_audio_new.setVisible(not use_existing)

    def browse_existing_audio(self):
        path, _ = QFileDialog.getOpenFileName(self, "Chọn file audio chính", "", "Audio Files (*.mp3 *.wav)")
        if path:
            self.selected_existing_audio = path
            self.existing_audio_label.setText(os.path.basename(path))
        else:
            self.selected_existing_audio = None
            self.existing_audio_label.setText("(Chưa chọn)")

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

    def update_volume_label(self):
        self.volume_label.setText(f"{self.volume_slider.value()}%")

    def start_convert(self):
        use_existing_audio = self.radio_use_audio.isChecked()

        if use_existing_audio:
            if not self.selected_existing_audio or not os.path.exists(self.selected_existing_audio):
                self.append_log("⚠️ Vui lòng chọn file audio có sẵn!")
                return

            if not self.selected_video_path or not os.path.exists(self.selected_video_path):
                self.append_log("⚠️ Vui lòng chọn video mẫu!")
                return

            final_audio = self.selected_existing_audio
            self.append_log(f"ℹ️ Dùng file audio có sẵn: {final_audio}")

            video_output = final_audio.replace(".mp3", ".mp4")
            self.append_log("🎞️ Đang ghép với video mẫu và nhạc nền...")

            self.btn_start.setEnabled(False)
            self.btn_open.setEnabled(False)
            self.log_output.clear()
            self.progress_bar.setValue(0)

            self.merge_thread = MergeThread(
                self.selected_video_path,
                final_audio,
                video_output,
                music_path=self.selected_music_path,
                music_volume=self.volume_slider.value()
            )
            self.merge_thread.log_signal.connect(self.handle_log_signal)
            self.merge_thread.finished_signal.connect(self.merge_finished)
            self.merge_thread.start()

        else:
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
            self.progress_bar.setValue(0)
            self.btn_start.setEnabled(False)
            self.btn_open.setEnabled(False)

            self.thread = ConvertThread(
                topic, api_key, num_parts,
                video_path=self.selected_video_path,
                music_path=self.selected_music_path,
                music_volume=music_volume,
                voice=voice
            )
            self.thread.log_signal.connect(self.handle_log_signal)
            self.thread.finished_signal.connect(self.convert_finished)
            self.thread.start()

    def handle_log_signal(self, msg):
        # Cập nhật progress bar nếu msg dạng "⏳ Render: xx.xx%"
        if msg.startswith("⏳ Render:"):
            try:
                percent_str = msg.split("⏳ Render:")[1].strip().replace("%", "")
                percent = float(percent_str)
                self.progress_bar.setValue(int(percent))
            except Exception:
                self.log_output.append(msg)
        else:
            self.log_output.append(msg)

    def merge_finished(self, output_file):
        self.append_log(f"✅ Hoàn tất tạo video: {output_file}")
        self.final_output_file = output_file
        self.btn_open.setEnabled(True)
        self.btn_start.setEnabled(True)
        self.progress_bar.setValue(100)

    def append_log(self, msg):
        self.log_output.append(msg)

    def convert_finished(self, output_file):
        self.final_output_file = output_file
        self.btn_start.setEnabled(True)
        self.btn_open.setEnabled(True)
        self.append_log(f"✅ Đã tạo video: {output_file}")
        self.progress_bar.setValue(100)

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
