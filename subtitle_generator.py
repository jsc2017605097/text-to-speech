import os
import tempfile
import time
from typing import Callable, Optional
import whisper
import torch


def generate_subtitle(audio_file: str, model_name: str = "base", log_func: Optional[Callable[[str], None]] = None) -> str:
    """
    Tạo file phụ đề SRT từ file audio sử dụng Whisper local
    
    Args:
        audio_file: Đường dẫn đến file audio
        model_name: Tên model Whisper (tiny, base, small, medium, large)
        log_func: Hàm callback để log thông tin
        
    Returns:
        Đường dẫn đến file SRT đã tạo
    """
    
    def log(msg: str):
        if log_func:
            log_func(msg)
        else:
            print(msg)
    
    if not os.path.exists(audio_file):
        raise FileNotFoundError(f"Không tìm thấy file audio: {audio_file}")
    
    log(f"🤖 Đang tải Whisper model '{model_name}'...")
    
    # Tạo tên file output
    base_name = os.path.splitext(audio_file)[0]
    srt_file = f"{base_name}.srt"
    
    try:
        # Load model
        model = load_whisper_model(model_name, log_func)
        
        # Transcribe audio
        log("🎤 Đang chuyển đổi audio thành text...")
        result = transcribe_audio_local(model, audio_file, log_func)
        
        # Tạo file SRT từ result
        create_srt_file(result, srt_file, log_func)
        
        log(f"✅ Đã tạo phụ đề: {srt_file}")
        return srt_file
        
    except Exception as e:
        log(f"❌ Lỗi khi tạo phụ đề: {str(e)}")
        raise


def load_whisper_model(model_name: str, log_func: Optional[Callable[[str], None]] = None):
    """
    Load Whisper model với thông báo tiến trình
    """
    def log(msg: str):
        if log_func:
            log_func(msg)
        else:
            print(msg)
    
    # Kiểm tra GPU
    device = "cuda" if torch.cuda.is_available() else "cpu"
    log(f"🔧 Sử dụng device: {device}")
    
    # Thông tin về các model
    model_info = {
        "tiny": "~39MB - Nhanh nhất, chất lượng thấp",
        "base": "~74MB - Cân bằng tốc độ và chất lượng", 
        "small": "~244MB - Chất lượng tốt",
        "medium": "~769MB - Chất lượng cao",
        "large": "~1550MB - Chất lượng tốt nhất"
    }
    
    log(f"📥 Đang tải model '{model_name}' ({model_info.get(model_name, 'Unknown')})")
    
    try:
        model = whisper.load_model(model_name, device=device)
        log(f"✅ Đã tải model '{model_name}' thành công!")
        return model
    except Exception as e:
        log(f"❌ Lỗi khi tải model: {str(e)}")
        raise


def transcribe_audio_local(model, audio_file: str, log_func: Optional[Callable[[str], None]] = None) -> dict:
    """
    Transcribe audio file sử dụng Whisper local model
    """
    def log(msg: str):
        if log_func:
            log_func(msg)
        else:
            print(msg)
    
    log("🔄 Đang xử lý audio file...")
    
    # Transcribe với word-level timestamps
    result = model.transcribe(
        audio_file,
        language="vi",  # Tiếng Việt
        word_timestamps=True,
        verbose=False
    )
    
    log("✅ Transcription hoàn tất!")
    return result


def create_srt_file(result: dict, output_file: str, log_func: Optional[Callable[[str], None]] = None):
    """
    Tạo file SRT từ kết quả transcription của Whisper
    """
    
    def log(msg: str):
        if log_func:
            log_func(msg)
        else:
            print(msg)
    
    def format_timestamp(seconds: float) -> str:
        """Chuyển đổi seconds thành định dạng SRT (HH:MM:SS,mmm)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        milliseconds = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"
    
    log("📝 Đang tạo file SRT...")
    
    with open(output_file, "w", encoding="utf-8") as f:
        if "segments" in result:
            # Xử lý từng segment
            for i, segment in enumerate(result["segments"], 1):
                start_time = format_timestamp(segment["start"])
                end_time = format_timestamp(segment["end"])
                text = segment["text"].strip()
                
                # Chia text dài thành nhiều dòng
                lines = split_text_into_lines(text, max_chars=50)
                
                f.write(f"{i}\n")
                f.write(f"{start_time} --> {end_time}\n")
                f.write(f"{lines}\n\n")
        else:
            # Fallback: tạo một segment duy nhất cho toàn bộ text
            text = result.get("text", "").strip()
            if text:
                # Ước tính thời gian dựa trên độ dài text
                words = text.split()
                duration = max(len(words) / 2.5, 5)  # Khoảng 2.5 từ/giây
                
                lines = split_text_into_lines(text, max_chars=50)
                
                f.write("1\n")
                f.write(f"00:00:00,000 --> {format_timestamp(duration)}\n")
                f.write(f"{lines}\n\n")
    
    log(f"✅ Đã lưu file SRT: {output_file}")


def split_text_into_lines(text: str, max_chars: int = 50) -> str:
    """
    Chia text thành nhiều dòng để dễ đọc trong subtitle
    """
    words = text.split()
    lines = []
    current_line = ""
    
    for word in words:
        if len(current_line + " " + word) <= max_chars:
            current_line += (" " + word) if current_line else word
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    
    if current_line:
        lines.append(current_line)
    
    return "\n".join(lines)


def create_optimized_segments(result: dict, max_segment_length: int = 10) -> dict:
    """
    Tối ưu hóa segments để có độ dài phù hợp cho subtitle
    """
    if "segments" not in result:
        return result
    
    optimized_segments = []
    
    for segment in result["segments"]:
        duration = segment["end"] - segment["start"]
        text = segment["text"].strip()
        
        if duration <= max_segment_length:
            optimized_segments.append(segment)
        else:
            # Chia segment dài thành các phần nhỏ hơn
            words = text.split()
            if len(words) <= 1:
                optimized_segments.append(segment)
                continue
                
            # Chia đều thời gian cho các từ
            time_per_word = duration / len(words)
            
            # Nhóm từ thành các segment ngắn hơn
            words_per_segment = max(1, int(max_segment_length / time_per_word))
            
            for i in range(0, len(words), words_per_segment):
                word_group = words[i:i + words_per_segment]
                segment_text = " ".join(word_group)
                
                start_time = segment["start"] + i * time_per_word
                end_time = min(segment["start"] + (i + len(word_group)) * time_per_word, segment["end"])
                
                optimized_segments.append({
                    "start": start_time,
                    "end": end_time,
                    "text": segment_text
                })
    
    result["segments"] = optimized_segments
    return result


def check_whisper_installation():
    """
    Kiểm tra xem Whisper đã được cài đặt chưa
    """
    try:
        import whisper
        return True
    except ImportError:
        return False


def install_whisper_guide():
    """
    Hướng dẫn cài đặt Whisper
    """
    guide = """
    ❌ Chưa cài đặt OpenAI Whisper!
    
    Để sử dụng tính năng tạo phụ đề, vui lòng cài đặt Whisper:
    
    1. Cài đặt qua pip:
       pip install openai-whisper
    
    2. Hoặc cài đặt từ GitHub (phiên bản mới nhất):
       pip install git+https://github.com/openai/whisper.git
    
    3. Cài đặt thêm ffmpeg (nếu chưa có):
       - Windows: Tải từ https://ffmpeg.org/download.html
       - macOS: brew install ffmpeg
       - Linux: sudo apt install ffmpeg
    
    4. Để sử dụng GPU (tùy chọn, tăng tốc độ):
       pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
    """
    return guide


# Hàm test để kiểm tra
def test_subtitle_generation():
    """
    Hàm test - chỉ sử dụng khi có file audio hợp lệ
    """
    if not check_whisper_installation():
        print(install_whisper_guide())
        return
    
    # Thay đổi các giá trị này để test
    test_audio = "test_audio.mp3"
    test_model = "base"
    
    def test_log(msg):
        print(f"[TEST] {msg}")
    
    try:
        subtitle_file = generate_subtitle(test_audio, test_model, test_log)
        print(f"Test thành công! File SRT: {subtitle_file}")
    except Exception as e:
        print(f"Test thất bại: {e}")


if __name__ == "__main__":
    print("Whisper Local Subtitle Generator")
    print("=" * 40)
    
    if check_whisper_installation():
        print("✅ Whisper đã sẵn sàng!")
        print("Sử dụng hàm generate_subtitle() để tạo phụ đề từ file audio")
    else:
        print(install_whisper_guide())
    
    # Uncomment dòng dưới để test
    # test_subtitle_generation()