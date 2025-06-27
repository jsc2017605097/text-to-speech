import requests
import time
import traceback
import re
import asyncio
import edge_tts
import unicodedata
from pydub import AudioSegment
import os
import sys
import json

# Xác định đường dẫn ffmpeg khi đóng gói
if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
    ffmpeg_path = os.path.join(base_path, "ffmpeg.exe")
else:
    # Cần đảm bảo ffmpeg.exe có trong PATH hoặc cùng thư mục với script
    ffmpeg_path = "ffmpeg.exe"
AudioSegment.converter = ffmpeg_path

MODEL = "deepseek/deepseek-r1:free"
API_URL = "https://openrouter.ai/api/v1/chat/completions"

def get_mc_info(voice: str) -> dict:
    """
    Trả về thông tin MC dựa trên giọng đọc được chọn
    """
    voice_to_mc = {
        "vi-VN-NamMinhNeural": {
            "name": "Hoàng Minh",
            "gender": "nam",
            "description": "một người dẫn chương trình nam chuyên nghiệp, giọng điệu ấm áp, uy tín"
        },
        "vi-VN-HoaiMyNeural": {
            "name": "Hoài My", 
            "gender": "nữ",
            "description": "một người dẫn chương trình nữ chuyên nghiệp, giọng điệu ngọt ngào, thân thiện"
        }
    }
    
    return voice_to_mc.get(voice, {
        "name": "MC",
        "gender": "chưa xác định", 
        "description": "một người dẫn chương trình chuyên nghiệp"
    })

def generate_dynamic_opening(topic: str, channel_name: str, call_openrouter_func) -> str:
    """
    Tạo lời mở đầu động dựa trên chủ đề Phật pháp cụ thể
    """
    opening_prompt = f"""
Tạo một lời mở đầu cực kỳ hấp dẫn và chạm đến tâm hồn cho chủ đề Phật pháp: "{topic}"

YÊU CẦU QUAN TRỌNG:
1. KHÔNG sử dụng tên MC hay giới thiệu kênh một cách cứng nhắc
2. Bắt đầu bằng một câu hỏi sâu sắc về cuộc sống HOẶC một tình huống thực tế mà ai cũng từng trải qua
3. Kết nối trực tiếp với khổ đau, thắc mắc, hay khát vọng tâm linh của con người hiện đại
4. Sử dụng ngôn ngữ gần gũi, ấm áp, như đang trò chuyện với người thân
5. Tối đa 3-4 câu, tạo cảm giác "tôi cần nghe điều này ngay bây giờ"
6. Kết thúc bằng việc hứa hẹn sẽ mang đến sự an yên, giải thoát hoặc hiểu biết sâu sắc

PHONG CÁCH PHẬT PHÁP MONG MUỐN:
- "Bạn có bao giờ cảm thấy trống rỗng giữa cuộc sống bon chen này không?"
- "Tại sao chúng ta càng có nhiều thứ, lòng càng thấy thiếu thốn?"
- "Có phải đêm nào bạn cũng thắc mắc ý nghĩa thật sự của cuộc đời?"
- "Khi đau khổ ập đến, làm sao để tâm hồn không bị cuốn theo?"
- "Đức Phật đã nói một câu khiến hàng triệu người thay đổi cuộc đời..."

TUYỆT ĐỐI TRÁNH:
- "Xin chào quý Phật tử..."
- "Nam mô A Di Đà Phật..." (ở đầu video)
- "Hôm nay chúng ta học về..."
- "Kinh Phật có nói..."
- Ngôn ngữ quá trang trọng, xa lạ

HƯỚNG TẬP TRUNG:
- Kết nối với đời sống thực tế (stress công việc, mối quan hệ, lo âu...)
- Tạo cảm giác đồng cảm sâu sắc
- Hứa hẹn giải pháp thiết thực từ Phật pháp
- Tránh thuật ngữ Phật học khó hiểu ngay từ đầu

Chỉ trả về nội dung lời mở đầu, không giải thích thêm.
"""

    messages = [
        {
            "role": "system", 
            "content": "Bạn là chuyên gia viết lời mở đầu cho nội dung Phật pháp, biết cách kết nối giáo lý với cuộc sống hiện đại một cách tự nhiên và chạm đến tâm hồn người nghe. Bạn hiểu rằng người xem cần cảm thấy Phật pháp thiết thực và gần gũi với cuộc sống của họ."
        },
        {"role": "user", "content": opening_prompt}
    ]
    
    opening = call_openrouter_func(messages)
    return opening.strip() if opening else ""
def slugify(text: str) -> str:
    # Chuyển Unicode về ASCII, lowercase, thay ký tự không alnum thành dấu '-'
    text = unicodedata.normalize('NFD', text)
    text = text.encode('ascii', 'ignore').decode('utf-8')
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-')

def clean_for_tts(text: str) -> str:
    """
    Làm sạch văn bản để chuyển sang TTS:
    - Giữ lại chữ cái (cả tiếng Việt), số và dấu câu cơ bản
    - Loại bỏ ký tự đặc biệt, dấu ngoặc, markdown...
    - Loại bỏ các câu mời xem "tuần sau", "tập tiếp theo"
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
    text = re.split(r"(?m)^(Nếu bạn muốn|---\s*PHẦN\s*\d+\s*---)", text)[0]
    
    # LOẠI BỎ CÁC CÂU MỜI XEM TUẦN SAU/TẬP TIẾP THEO
    text = re.sub(r".*?(tuần sau|tập tiếp theo|chương trình tuần tới|hẹn gặp lại.*?tuần|xem tiếp.*?tuần).*?[\.\!]", "", text, flags=re.IGNORECASE)
    text = re.sub(r".*?(kính mời.*?xem.*?vào).*?[\.\!]", "", text, flags=re.IGNORECASE)
    text = re.sub(r".*?(đừng quên theo dõi|đăng ký kênh).*?[\.\!]", "", text, flags=re.IGNORECASE)

    # Chỉ giữ lại các ký tự hợp lệ cho TTS: chữ cái (có dấu), số, dấu câu cơ bản và khoảng trắng
    text = re.sub(r"[^a-zA-ZÀ-ỹ0-9\s\.,!?:;\-…]", "", text)

    # Rút gọn khoảng trắng
    text = re.sub(r"\s+", " ", text).strip()

    return text

async def create_audio_from_text(text: str, output_path: str, voice: str = "vi-VN-NamMinhNeural"):
    communicate = edge_tts.Communicate(text=text, voice=voice)
    await communicate.save(output_path)

def merge_audio_files(output_file: str, pattern: str, num_parts: int):
    print("\n🔄 Đang gộp các phần âm thanh lại thành 1 file...")
    merged = AudioSegment.empty()
    for i in range(num_parts):
        part_file = pattern.format(i + 1)
        if os.path.exists(part_file):
            audio = AudioSegment.from_file(part_file, format="mp3")
            merged += audio
        else:
            print(f"⚠️ Không tìm thấy: {part_file}, bỏ qua.")
    merged.export(output_file, format="mp3")
    print(f"✅ Đã tạo file gộp: {output_file}")

def parse_detailed_outline(outline_content: str) -> list:
    """
    Parse detailed outline from JSON format or fallback to simple parsing
    """
    try:
        # Try to parse as JSON first
        outline_data = json.loads(outline_content)
        if isinstance(outline_data, list):
            return outline_data
        elif isinstance(outline_data, dict) and 'outline' in outline_data:
            return outline_data['outline']
    except:
        pass
    
    # Fallback to simple parsing
    outline_points = []
    lines = outline_content.split('\n')
    current_section = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Check if it's a numbered section (1., 2., etc.)
        if re.match(r'^\d+\.', line):
            if current_section:
                outline_points.append(current_section)
            current_section = {
                'title': line,
                'content': '',
                'key_points': [],
                'emotion': '',
                'transition': ''
            }
        elif current_section and line:
            # Add content to current section
            if current_section['content']:
                current_section['content'] += ' ' + line
            else:
                current_section['content'] = line
    
    # Add the last section
    if current_section:
        outline_points.append(current_section)
    
    return outline_points

def generate_chapter_timestamps(outline_sections: list, output_dir: str, base_filename: str):
    chapter_lines = []
    current_time_ms = 0

    for idx, section in enumerate(outline_sections):
        # Load thời lượng audio tương ứng
        audio_file = os.path.join(output_dir, f"{base_filename}-part-{idx+1}.mp3")
        if not os.path.exists(audio_file):
            continue

        audio = AudioSegment.from_file(audio_file)
        timestamp = time.strftime('%M:%S', time.gmtime(current_time_ms // 1000))
        
        # Lấy tiêu đề ngắn gọn
        title_line = section.get('title', f"Phần {idx+1}")
        chapter_lines.append(f"{timestamp} - {title_line.strip()}")

        current_time_ms += len(audio)

    chapter_text = '\n'.join(chapter_lines)
    chapter_file = os.path.join(output_dir, f"{base_filename}-chapters.txt")
    with open(chapter_file, "w", encoding="utf-8") as f:
        f.write(chapter_text)

    return chapter_file

def generate_buddhist_topic(call_openrouter_func, channel_name: str = "Pháp Âm Bình An") -> str:
   """
   Sinh ngẫu nhiên một chủ đề Phật pháp ý nghĩa, dễ viral, mang tính chữa lành
   """
   prompt = f"""
Tạo một tiêu đề bài giảng Phật pháp hấp dẫn cho kênh YouTube "{channel_name}".

YÊU CẦU:
- Tối đa 10-12 từ, ngắn gọn dễ nhớ
- Kết nối với khổ đau, lo âu thực tế của người hiện đại
- Sử dụng ngôn ngữ đời thường, tránh thuật ngữ Phật học khó hiểu
- Tạo cảm giác cấp thiết: "Tôi cần nghe điều này ngay"
- Có thể dùng dạng câu hỏi hoặc câu khẳng định

MẪU THAM KHẢO:
✅ "Tại sao buông bỏ lại khó đến thế?"
✅ "Ba điều Phật dạy giúp tâm bình an"
✅ "Khi đau khổ, hãy nhớ lời này của Phật"
✅ "Sức mạnh kỳ diệu của lòng từ bi"
✅ "Đi qua tổn thương để tìm lại chính mình"

TRÁNH:
❌ "Giáo lý Tứ Diệu Đế trong kinh Pháp Cú"
❌ "Phân tích Bát Chánh Đạo theo truyền thống Nguyên Thủy"
❌ Từ ngữ quá trang trọng, xa lạ

Chỉ trả về 1 tiêu đề duy nhất, không giải thích.
"""
   messages = [
       {"role": "system", "content": "Bạn là người chuyên đặt tiêu đề sâu sắc, dễ lan tỏa cho nội dung Phật pháp."},
       {"role": "user", "content": prompt}
   ]
   result = call_openrouter_func(messages)
   return result.strip() if result else "Tại sao tâm ta luôn bất an?"

def run_convert(
    topic: str,
    api_key: str,
    num_parts: int = 12,
    log_func=print,
    voice: str = "vi-VN-NamMinhNeural",
    channel_name: str = "Pháp Âm Bình An"
) -> str:
    HEADERS = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    def call_openrouter(messages):
        try:
            data = {"model": MODEL, "messages": messages}
            res = requests.post(API_URL, headers=HEADERS, json=data)
            if res.status_code != 200:
                log_func(f"❌ HTTP {res.status_code} - {res.text}")
                return None
            return res.json()["choices"][0]["message"]["content"]
        except Exception:
            log_func("❌ Lỗi khi gọi API:")
            log_func(traceback.format_exc())
            return None

    if not topic:
        log_func("🎲 Đang tự tạo chủ đề Phật pháp...")
        topic = generate_buddhist_topic(call_openrouter, channel_name)
        log_func(f"🎯 Chủ đề được tạo: {topic}")
    else:
        log_func(f"🚀 Bắt đầu chạy với chủ đề: {topic}")
    

    log_func(f"🔑 Dùng API key: {api_key[:6]}***")
    log_func(f"📄 Số phần dự kiến: {num_parts}")
    log_func(f"🎤 Giọng đọc: {voice}")
    log_func(f"📺 Kênh: {channel_name}")

    # Lấy thông tin MC dựa trên giọng đọc
    mc_info = get_mc_info(voice)
    mc_name = mc_info["name"]
    mc_gender = mc_info["gender"]
    mc_description = mc_info["description"]
    
    log_func(f"🎭 MC được chọn: {mc_name} ({mc_gender})")


    base = slugify(topic)
    output_dir = os.path.join("output", base)
    os.makedirs(output_dir, exist_ok=True)

    output_script = os.path.join(output_dir, f"{base}.txt")
    output_clean = os.path.join(output_dir, f"{base}-clean.txt")
    output_outline = os.path.join(output_dir, f"{base}-outline.txt")


    # Clear previous output files if they exist for a fresh run
    for file_path in [output_script, output_clean, output_outline]:
        if os.path.exists(file_path):
            os.remove(file_path)

    # Step 1: Generate a detailed Buddhist teaching outline
    log_func("\n📝 Đang tạo dàn ý bài giảng Phật pháp chi tiết...")
    outline_prompt = f"""
Dựa trên chủ đề Phật pháp: '{topic}', hãy tạo một dàn ý bài giảng Phật pháp CỰC KỲ CHI TIẾT để chia thành {num_parts} phân đoạn.

QUAN TRỌNG: Đây là một bài giảng Phật pháp LIỀN MẠCH được ghép thành 1 file audio duy nhất, KHÔNG phải {num_parts} bài giảng riêng biệt.

Mỗi phân đoạn phải có:
1. Tiêu đề rõ ràng liên quan đến giáo lý Phật
2. Nội dung Phật pháp cụ thể cần trình bày (3-5 câu mô tả chi tiết)
3. Kinh văn hoặc lời Phật dạy liên quan (nếu có)
4. Ý nghĩa tu học và áp dụng trong đời sống
5. Cách chuyển tiếp sang phần tiếp theo (LIỀN MẠCH, không có "buổi sau")
6. Câu chuyện, ví dụ minh họa từ Phật sử hoặc đời sống thực tế

Định dạng trả về:
```
1. [Tiêu đề phần 1]
   Nội dung Phật pháp: [Mô tả cụ thể 3-5 câu về giáo lý sẽ trình bày]
   Kinh văn/Lời Phật: [Trích dẫn kinh văn hoặc lời Phật dạy liên quan]
   Ý nghĩa tu học: [Cách áp dụng trong đời sống, tu tập]
   Câu chuyện minh họa: [Ví dụ, câu chuyện minh họa]
   Chuyển tiếp: [Cách dẫn dắt sang phần tiếp theo NGAY LẬP TỨC]

2. [Tiêu đề phần 2]
   Nội dung Phật pháp: [Mô tả cụ thể...]
   Kinh văn/Lời Phật: [...]
   Ý nghĩa tu học: [...]
   Câu chuyện minh họa: [...]
   Chuyển tiếp: [...]

...và tiếp tục cho đến phần {num_parts}
```

Đảm bảo:
- Logic giáo lý liên kết chặt chẽ giữa các phần LIỀN MẠCH
- Mỗi phần chuyển tiếp tự nhiên sang phần tiếp theo trong cùng 1 bài giảng
- Cung cấp đủ chi tiết về giáo lý Phật để trình bày mà không bị lạc chủ đề
- Bài giảng có cấu trúc rõ ràng (dẫn nhập → triển khai giáo lý → ứng dụng → kết luận)
- Sử dụng ngôn ngữ Phật pháp chính xác, dễ hiểu
- Tích hợp câu chuyện Phật sử, ví dụ thực tế để minh họa
"""

    outline_messages = [
        {
            "role": "system",
            "content": (
                "Bạn là một vị thầy giảng Phật pháp có kiến thức sâu sắc về giáo lý Phật giáo, "
                "chuyên tạo dàn ý bài giảng chi tiết cho chương trình Phật pháp LIỀN MẠCH. "
                "Phải tạo dàn ý CỰC KỲ CHI TIẾT dựa trên giáo lý chính thống, "
                "kết hợp kinh văn, lời Phật dạy và ứng dụng thực tế trong đời sống. "
                "KHÔNG được có bất kỳ mention nào về 'buổi sau', 'bài tiếp theo' vì đây là 1 bài giảng liền mạch. "
                "Sử dụng ngôn ngữ Phật pháp chính xác, tôn kính nhưng dễ hiểu."
            )
        },
        {"role": "user", "content": outline_prompt}
    ]
    
    outline_content = call_openrouter(outline_messages)
    if not outline_content:
        log_func("❌ Không thể tạo dàn ý. Dừng chương trình.")
        return ""
    
    # Save detailed outline
    with open(output_outline, "w", encoding="utf-8") as f:
        f.write(f"DÀN Ý BÀI GIẢNG PHẬT PHÁP CHI TIẾT: {topic}\n")
        f.write(f"KÊNH: {channel_name}\n")
        f.write(f"THẦY GIẢNG: {mc_name} ({mc_gender})\n")
        f.write("="*50 + "\n\n")
        f.write(outline_content)
    
    log_func("✅ Đã tạo dàn ý bài giảng chi tiết, lưu tại: " + output_outline)
    
    # Parse the detailed outline
    outline_sections = parse_detailed_outline(outline_content)
    if not outline_sections:
        # Fallback parsing for non-JSON format
        sections = re.split(r'\n(?=\d+\.)', outline_content.strip())
        outline_sections = []
        for section in sections:
            if section.strip():
                lines = section.strip().split('\n')
                title = lines[0] if lines else ""
                content = '\n'.join(lines[1:]) if len(lines) > 1 else ""
                outline_sections.append({
                    'title': title,
                    'content': content,
                    'full_text': section.strip()
                })
    
    log_func(f"📋 Đã phân tích {len(outline_sections)} phần trong dàn ý")
    
    # Generate dynamic Buddhist opening
    log_func("\n🎭 Đang tạo lời mở đầu Phật pháp...")
    dynamic_opening = generate_dynamic_opening(topic, channel_name, call_openrouter)
    if dynamic_opening:
        log_func("✅ Đã tạo lời mở đầu Phật pháp")
    else:
        log_func("⚠️ Không thể tạo lời mở đầu, sẽ dùng mặc định")
        dynamic_opening = ""
    
    # Store the full teaching text to pass context between parts
    full_teaching_text = ""
    
    for i in range(num_parts):
        log_func(f"\n🟡 Đang viết phần {i+1}/{num_parts}...")
        
        # Get the specific outline section for this part
        if i < len(outline_sections):
            current_section = outline_sections[i]
            section_guide = current_section.get('full_text', current_section.get('content', ''))
        else:
            # If we have fewer outline sections than num_parts, use the last one
            current_section = outline_sections[-1] if outline_sections else {}
            section_guide = "Tiếp tục phát triển giáo lý theo logic tự nhiên"
        
        # Prepare context from previous parts (last 1500 chars to manage tokens)
        context_text = full_teaching_text[-1500:] if full_teaching_text else ""
        
        # Create detailed prompt based on part position
        if i == 0:
            # Use dynamic opening for first part
            opening_instruction = f"""
SỬ DỤNG LỜI MỞ ĐẦU PHẬT PHÁP SAU ĐÂY:
"{dynamic_opening}"

Sau đó tiếp tục phát triển nội dung giáo lý theo hướng dẫn bên dưới.
""" if dynamic_opening else """
Tạo lời mở đầu Phật pháp bằng cách:
- Bắt đầu với lời chào tôn kính: "Nam mô Bổn Sư Thích Ca Mâu Ni Phật"
- Lời chào ấm áp đến Phật tử: "Kính chào quý Phật tử thân mến"
- Giới thiệu chủ đề một cách gây tò mò về giáo lý sẽ học
- Tạo cảm giác thiêng liêng, tôn kính ngay từ đầu
"""

            user_prompt_content = f"""
Viết phần mở đầu bài giảng Phật pháp dựa trên chủ đề: '{topic}'

{opening_instruction}

HƯỚNG DẪN CHI TIẾT CHO PHẦN NÀY:
{section_guide}

YÊU CẦU VIẾT:
- Khoảng 500 từ
- Giọng điệu tôn kính, ấm áp như một vị thầy giảng Phật pháp
- Sử dụng ngôn ngữ Phật pháp chính xác nhưng dễ hiểu
- TUÂN THỦ CHẶT CHẾ nội dung giáo lý trong hướng dẫn trên
- KHÔNG lệch khỏi giáo lý chính thống hoặc thêm thông tin sai lệch
- KHÔNG sử dụng ký hiệu đặc biệt, dấu ngoặc, markdown
- Chỉ dùng dấu câu thông thường: . , ! ? : ;
- ĐÂY LÀ BÀI GIẢNG LIỀN MẠCH, KHÔNG được có "buổi sau", "bài tiếp theo"
- Có thể nhắc đến "{channel_name}" một cách tự nhiên nếu phù hợp
- Tích hợp lời Phật dạy, kinh văn nếu có trong hướng dẫn

Chỉ trả về nội dung bài giảng, không thêm giải thích hay meta.
"""
        elif i == num_parts - 1:
            user_prompt_content = f"""
Viết phần kết thúc bài giảng Phật pháp dựa trên chủ đề: '{topic}'

HƯỚNG DẪN CHI TIẾT CHO PHẦN NÀY:
{section_guide}

NỐI TIẾP TỪ PHẦN TRƯỚC:
{context_text}

YÊU CẦU VIẾT:
- Khoảng 500 từ
- Kết thúc bài giảng có ý nghĩa sâu sắc về giáo lý
- Tóm tắt những điểm chính của bài giảng
- Khuyến khích Phật tử áp dụng vào đời sống tu tập
- Kết thúc bằng lời cầu nguyện: "Nguyện tất cả chúng sinh được hạnh phúc, an lạc, giải thoát khỏi mọi khổ đau. Nam mô Bổn Sư Thích Ca Mâu Ni Phật"
- Lời cảm ơn Phật tử: "Cảm ơn quý Phật tử đã cùng học tập giáo lý. Mong rằng những lời Phật dạy hôm nay sẽ mang lại lợi ích cho đời sống tu tập của quý vị. Hẹn gặp lại quý Phật tử trong những bài giảng tiếp theo"
- Giọng điệu tôn kính, ấm áp, chân thành
- TUÂN THỦ CHẶT CHẾ nội dung giáo lý trong hướng dẫn
- Nối tiếp tự nhiên từ phần trước, KHÔNG lặp lại nội dung
- KHÔNG sử dụng ký hiệu đặc biệt, dấu ngoặc, markdown
- Chỉ dùng dấu câu thông thường
- ĐÂY LÀ KẾT THÚC BÀI GIẢNG, KHÔNG có "buổi sau"

Chỉ trả về nội dung bài giảng, không thêm giải thích hay meta.
"""
        else:
            user_prompt_content = f"""
Viết tiếp phần {i+1} bài giảng Phật pháp dựa trên chủ đề: '{topic}'

HƯỚNG DẪN CHI TIẾT CHO PHẦN NÀY:
{section_guide}

NỐI TIẾP TỪ PHẦN TRƯỚC:
{context_text}

YÊU CẦU VIẾT:
- Khoảng 500 từ
- Giọng điệu tôn kính, trầm ổn như vị thầy giảng Phật pháp
- Sử dụng ngôn ngữ Phật pháp chính xác, dễ hiểu
- TUÂN THỦ CHẶT CHẾ nội dung giáo lý trong hướng dẫn trên
- Nối tiếp tự nhiên từ phần trước, KHÔNG lặp lại nội dung
- Phát triển giáo lý theo đúng hướng đã định trong dàn ý
- Tích hợp kinh văn, lời Phật dạy nếu có trong hướng dẫn
- Sử dụng câu chuyện Phật sử, ví dụ thực tế để minh họa
- Có thể sử dụng các câu giao tiếp với Phật tử như "Quý Phật tử có biết rằng...", "Đức Phật dạy rằng...", "Chúng ta cùng suy ngẫm..."
- KHÔNG sử dụng ký hiệu đặc biệt, dấu ngoặc, markdown
- Chỉ dùng dấu câu thông thường
- ĐÂY LÀ BÀI GIẢNG LIỀN MẠCH, TUYỆT ĐỐI KHÔNG được có "buổi sau", "bài tiếp theo"
- Chuyển tiếp tự nhiên sang phần tiếp theo TRONG CÙNG BÀI GIẢNG

Chỉ trả về nội dung bài giảng, không thêm giải thích hay meta.
"""

        messages = [
            {
                "role": "system",
                "content": (
                    f"Bạn là một vị thầy giảng Phật pháp chuyên nghiệp của kênh '{channel_name}', "
                    "có kiến thức sâu sắc về giáo lý Phật giáo, khả năng truyền đạt Phật pháp dễ hiểu "
                    "và tạo kết nối tâm linh với Phật tử. "
                    "PHẢI tuân thủ chặt chẽ giáo lý chính thống và hướng dẫn được cung cấp. "
                    "KHÔNG được lệch khỏi giáo lý Phật hoặc tự ý thêm nội dung không chính xác. "
                    "ĐÂY LÀ BÀI GIẢNG LIỀN MẠCH, TUYỆT ĐỐI KHÔNG được mention 'buổi sau', 'bài tiếp theo'. "
                    "Sử dụng ngôn ngữ Phật pháp tôn kính nhưng dễ hiểu. "
                    "CHỈ trả về nội dung bài giảng, không thêm bất kỳ meta hay giải thích nào."
                )
            },
            {"role": "user", "content": user_prompt_content}
        ]

        reply = call_openrouter(messages)
        
        if not reply or len(reply.strip()) < 50:
            log_func(f"⚠️ Phần {i+1} rỗng hoặc quá ngắn, bỏ qua.")
            continue
        
        log_func(f"✅ Đã viết xong phần {i+1}. Đang xử lý...")
        
        # Update full teaching context
        full_teaching_text += reply.strip() + "\n"

        # Save raw content
        with open(output_script, "a", encoding="utf-8") as f:
            f.write(f"\n--- PHẦN {i+1} ---\n")
            if i == 0 and dynamic_opening:
                f.write(f"[Lời mở đầu Phật pháp: {dynamic_opening}]\n\n")
            f.write(reply.strip() + "\n")

        # Clean and save for TTS
        cleaned = clean_for_tts(reply)
        with open(output_clean, "a", encoding="utf-8") as f: 
            f.write(f"\n--- PHẦN {i+1} ---\n")
            f.write(cleaned + "\n")

        # Generate audio
        audio_file = os.path.join(output_dir, f"{base}-part-{i+1}.mp3")
        asyncio.run(create_audio_from_text(cleaned, audio_file, voice))
        log_func(f"🎧 Đã tạo file âm thanh: {audio_file}")

        time.sleep(10)  # Rate limiting

    # Merge all audio files
    final_audio = os.path.join(output_dir, f"{base}-final.mp3")
    merge_audio_files(
        final_audio,
        os.path.join(output_dir, f"{base}-part-{{}}.mp3"),
        num_parts
    )

    # Tạo chapter timestamps cho bài giảng Phật pháp
    chapter_file = generate_chapter_timestamps(outline_sections, output_dir, base)
    log_func(f"📍 Đã tạo file chapter: {chapter_file}")

    
    log_func(f"\n🎉 Hoàn tất bài giảng Phật pháp!")
    log_func(f"📺 Kênh: {channel_name}")
    log_func(f"📄 Dàn ý bài giảng: {output_outline}")
    log_func(f"📝 Kịch bản bài giảng: {output_script}")
    log_func(f"🧹 Kịch bản clean: {output_clean}")
    log_func(f"🎵 Audio bài giảng hoàn chỉnh: {final_audio}")
    
    return final_audio
