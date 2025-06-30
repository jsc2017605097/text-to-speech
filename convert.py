import asyncio
import edge_tts
import unicodedata
from pydub import AudioSegment
import os
import sys
import re
import time

# Xác định đường dẫn ffmpeg khi đóng gói
if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
    ffmpeg_path = os.path.join(base_path, "ffmpeg.exe")
else:
    # Cần đảm bảo ffmpeg.exe có trong PATH hoặc cùng thư mục với script
    ffmpeg_path = "ffmpeg.exe"
AudioSegment.converter = ffmpeg_path

def clean_for_tts(text: str) -> str:
    """
    Làm sạch văn bản để chuyển sang TTS:
    - Giữ lại chữ cái (cả tiếng Việt), số và dấu câu cơ bản
    - Loại bỏ ký tự đặc biệt, dấu ngoặc, markdown...
    """
    import unicodedata

    # Chuẩn hóa Unicode để tránh ký tự lạ
    text = unicodedata.normalize('NFKC', text)

    # Loại bỏ markdown ** ** hoặc * *
    text = re.sub(r"\*\*.*?\*\*", "", text)
    text = re.sub(r"\*.*?\*", "", text)

    # Xóa nội dung trong ngoặc tròn ( ), vuông [ ], nhọn < >, ngoặc kép
    text = re.sub(r"[\(\)\[\]\{\}<>\"""''']", "", text)

    # Xóa các hướng dẫn như "Camera:..." hoặc "--- PHẦN X ---"
    text = re.sub(r"Camera.*?\.", "", text)
    text = re.sub(r"(?m)^---.*?---", "", text)
    
    # Chỉ giữ lại các ký tự hợp lệ cho TTS: chữ cái (có dấu), số, dấu câu cơ bản và khoảng trắng
    text = re.sub(r"[^a-zA-ZÀ-ỹ0-9\s\.,!?:;\-…]", "", text)

    # Rút gọn khoảng trắng
    text = re.sub(r"\s+", " ", text).strip()

    return text

def split_text_by_length(text: str, max_length: int = 5000) -> list:
    """
    Chia văn bản thành các phần nhỏ hơn dựa trên độ dài ký tự
    Ưu tiên cắt tại dấu câu để giữ tính tự nhiên
    """
    if len(text) <= max_length:
        return [text]
    
    parts = []
    current_pos = 0
    
    while current_pos < len(text):
        # Lấy đoạn text có độ dài tối đa
        end_pos = min(current_pos + max_length, len(text))
        
        # Nếu chưa hết văn bản, tìm vị trí cắt tốt nhất
        if end_pos < len(text):
            # Tìm dấu câu gần nhất trong khoảng 500 ký tự cuối
            best_cut = end_pos
            for i in range(max(current_pos + max_length - 500, current_pos), end_pos):
                if text[i] in '.!?;':
                    best_cut = i + 1
                    break
            end_pos = best_cut
        
        part = text[current_pos:end_pos].strip()
        if part:
            parts.append(part)
        
        current_pos = end_pos
    
    return parts

def split_text_by_sentences(text: str, max_sentences: int = 50) -> list:
    """
    Chia văn bản thành các phần dựa trên số câu
    """
    # Tách câu dựa trên dấu câu
    sentences = re.split(r'[.!?;]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    
    if len(sentences) <= max_sentences:
        return [text]
    
    parts = []
    current_part = []
    
    for sentence in sentences:
        current_part.append(sentence)
        
        if len(current_part) >= max_sentences:
            parts.append('. '.join(current_part) + '.')
            current_part = []
    
    # Thêm phần cuối nếu còn
    if current_part:
        parts.append('. '.join(current_part) + '.')
    
    return parts

async def create_audio_from_text(text: str, output_path: str, voice: str = "vi-VN-NamMinhNeural"):
    """Tạo file audio từ text sử dụng Edge TTS"""
    try:
        communicate = edge_tts.Communicate(text=text, voice=voice)
        await communicate.save(output_path)
        return True
    except Exception as e:
        print(f"❌ Lỗi khi tạo audio: {e}")
        return False

def merge_audio_files(output_file: str, audio_files: list):
    """Gộp nhiều file audio thành một file duy nhất"""
    print(f"\n🔄 Đang gộp {len(audio_files)} file audio...")
    
    merged = AudioSegment.empty()
    successful_files = 0
    
    for audio_file in audio_files:
        if os.path.exists(audio_file):
            try:
                audio = AudioSegment.from_file(audio_file, format="mp3")
                merged += audio
                successful_files += 1
                print(f"✅ Đã thêm: {os.path.basename(audio_file)}")
            except Exception as e:
                print(f"⚠️ Lỗi khi đọc {audio_file}: {e}")
        else:
            print(f"⚠️ Không tìm thấy: {audio_file}")
    
    if successful_files > 0:
        merged.export(output_file, format="mp3")
        print(f"✅ Đã tạo file gộp: {output_file}")
        print(f"📊 Đã gộp {successful_files}/{len(audio_files)} file thành công")
        return True
    else:
        print("❌ Không có file audio nào để gộp")
        return False

def convert_text_file_to_speech(
    input_file: str,
    output_dir: str = None,
    voice: str = "vi-VN-NamMinhNeural",
    split_method: str = "length",  # "length" hoặc "sentences"
    max_length: int = 5000,
    max_sentences: int = 50,
    log_func=print
) -> str:
    """
    Convert file text thành speech
    
    Args:
        input_file: Đường dẫn file txt đầu vào
        output_dir: Thư mục output (mặc định cùng thư mục với input)
        voice: Giọng đọc Edge TTS
        split_method: Phương pháp chia text ("length" hoặc "sentences")
        max_length: Độ dài tối đa mỗi phần (khi dùng method "length")
        max_sentences: Số câu tối đa mỗi phần (khi dùng method "sentences")
        log_func: Hàm để log
    
    Returns:
        Đường dẫn file audio cuối cùng
    """
    
    if not os.path.exists(input_file):
        log_func(f"❌ Không tìm thấy file: {input_file}")
        return ""
    
    # Xác định thư mục output
    if output_dir is None:
        output_dir = os.path.dirname(input_file)
    os.makedirs(output_dir, exist_ok=True)
    
    # Tạo tên file output
    base_name = os.path.splitext(os.path.basename(input_file))[0]
    
    log_func(f"🚀 Bắt đầu convert: {input_file}")
    log_func(f"🎤 Giọng đọc: {voice}")
    log_func(f"📁 Thư mục output: {output_dir}")
    log_func(f"🔧 Phương pháp chia: {split_method}")
    
    # Đọc file text
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            original_text = f.read()
    except Exception as e:
        log_func(f"❌ Lỗi khi đọc file: {e}")
        return ""
    
    if not original_text.strip():
        log_func("❌ File text rỗng")
        return ""
    
    log_func(f"📄 Độ dài text gốc: {len(original_text)} ký tự")
    
    # Làm sạch text
    cleaned_text = clean_for_tts(original_text)
    log_func(f"🧹 Độ dài text sau khi làm sạch: {len(cleaned_text)} ký tự")
    
    # Lưu text đã làm sạch
    cleaned_file = os.path.join(output_dir, f"{base_name}-cleaned.txt")
    with open(cleaned_file, 'w', encoding='utf-8') as f:
        f.write(cleaned_text)
    log_func(f"✅ Đã lưu text làm sạch: {cleaned_file}")
    
    # Chia text thành các phần nhỏ
    if split_method == "sentences":
        text_parts = split_text_by_sentences(cleaned_text, max_sentences)
        log_func(f"📋 Chia theo câu: {len(text_parts)} phần (tối đa {max_sentences} câu/phần)")
    else:
        text_parts = split_text_by_length(cleaned_text, max_length)
        log_func(f"📋 Chia theo độ dài: {len(text_parts)} phần (tối đa {max_length} ký tự/phần)")
    
    # Tạo audio cho từng phần
    audio_files = []
    
    for i, part in enumerate(text_parts, 1):
        log_func(f"\n🟡 Đang xử lý phần {i}/{len(text_parts)}...")
        log_func(f"📏 Độ dài phần {i}: {len(part)} ký tự")
        
        # Tạo file audio cho phần này
        part_audio = os.path.join(output_dir, f"{base_name}-part-{i:03d}.mp3")
        
        success = asyncio.run(create_audio_from_text(part, part_audio, voice))
        
        if success:
            log_func(f"✅ Đã tạo: {os.path.basename(part_audio)}")
            audio_files.append(part_audio)
        else:
            log_func(f"❌ Lỗi tạo phần {i}")
        
        # Delay để tránh rate limit
        time.sleep(1)
    
    if not audio_files:
        log_func("❌ Không tạo được file audio nào")
        return ""
    
    # Gộp tất cả file audio
    final_audio = os.path.join(output_dir, f"{base_name}-final.mp3")
    
    if merge_audio_files(final_audio, audio_files):
        log_func(f"\n🎉 Hoàn thành!")
        log_func(f"🎵 File audio cuối cùng: {final_audio}")
        
        # Tính thời lượng file cuối
        try:
            final_audio_segment = AudioSegment.from_file(final_audio)
            duration_seconds = len(final_audio_segment) / 1000
            duration_minutes = int(duration_seconds // 60)
            duration_seconds = int(duration_seconds % 60)
            log_func(f"⏱️ Thời lượng: {duration_minutes}:{duration_seconds:02d}")
        except:
            pass
        
        # Tùy chọn: Xóa các file tạm
        cleanup = input("\n🗑️ Bạn có muốn xóa các file audio tạm không? (y/n): ").lower().strip()
        if cleanup == 'y':
            deleted = 0
            for audio_file in audio_files:
                try:
                    os.remove(audio_file)
                    deleted += 1
                except:
                    pass
            log_func(f"🗑️ Đã xóa {deleted} file tạm")
        
        return final_audio
    else:
        return ""

def main():
    """Hàm main để chạy từ command line"""
    print("🎙️ CHƯƠNG TRÌNH CHUYỂN ĐỔI TEXT-TO-SPEECH")
    print("="*50)
    
    # Nhập đường dẫn file
    input_file = input("📁 Nhập đường dẫn file txt: ").strip().strip('"')
    
    if not input_file:
        print("❌ Vui lòng nhập đường dẫn file")
        return
    
    # Chọn giọng đọc
    voices = {
        "1": ("vi-VN-NamMinhNeural", "Nam Minh (Nam)"),
        "2": ("vi-VN-HoaiMyNeural", "Hoài My (Nữ)"),
        "3": ("vi-VN-TuanNeural", "Tuấn (Nam)"),
        "4": ("vi-VN-VyNeural", "Vy (Nữ)")
    }
    
    print("\n🎤 Chọn giọng đọc:")
    for key, (voice_id, voice_name) in voices.items():
        print(f"  {key}. {voice_name}")
    
    voice_choice = input("Chọn (1-4, mặc định 1): ").strip() or "1"
    selected_voice = voices.get(voice_choice, voices["1"])[0]
    
    print(f"✅ Đã chọn: {voices.get(voice_choice, voices['1'])[1]}")
    
    # Chọn phương pháp chia text
    print("\n🔧 Chọn phương pháp chia text:")
    print("  1. Theo độ dài ký tự (khuyến nghị)")
    print("  2. Theo số câu")
    
    split_choice = input("Chọn (1-2, mặc định 1): ").strip() or "1"
    split_method = "length" if split_choice == "1" else "sentences"
    
    # Chạy convert
    result = convert_text_file_to_speech(
        input_file=input_file,
        voice=selected_voice,
        split_method=split_method
    )
    
    if result:
        print(f"\n🎊 THÀNH CÔNG! File audio đã được tạo tại: {result}")
    else:
        print("\n💥 Có lỗi xảy ra trong quá trình chuyển đổi")
    
    input("\nNhấn Enter để thoát...")

if __name__ == "__main__":
    main()