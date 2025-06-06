# batch_transcribe.py

import os
import whisper

def transcribe_to_srt(audio_path, language="vi"):
    """
    Chuyển file audio thành phụ đề SRT bằng Whisper.
    """
    print(f"🔊 Đang tạo phụ đề cho: {audio_path}")
    model = whisper.load_model("small")
    result = model.transcribe(audio_path, language=language, task="transcribe")
    print(f"✅ Đã tạo: {audio_path.replace('.mp3', '.srt')}")


def should_process(mp3_path):
    srt_path = mp3_path.replace(".mp3", ".srt")
    return not os.path.exists(srt_path)


def scan_output_folders(root_dir="output"):
    for topic_folder in os.listdir(root_dir):
        topic_path = os.path.join(root_dir, topic_folder)

        if not os.path.isdir(topic_path):
            continue  # bỏ qua file lạ

        for file in os.listdir(topic_path):
            if file.endswith("-final.mp3"):
                mp3_path = os.path.join(topic_path, file)
                if should_process(mp3_path):
                    try:
                        transcribe_to_srt(mp3_path)
                    except Exception as e:
                        print(f"❌ Lỗi khi xử lý {mp3_path}: {e}")
                else:
                    print(f"⏭️ Đã có srt: {mp3_path.replace('.mp3', '.srt')}, bỏ qua.")


if __name__ == "__main__":
    scan_output_folders()
