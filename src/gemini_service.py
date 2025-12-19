"""
Gemini Service - Tạo kịch bản bán hàng và voice sử dụng Google Gemini API
"""

import os
import json
import base64
import time
import tempfile
import subprocess
import struct
import wave
import shutil
from pathlib import Path
from typing import Optional, Tuple
from dataclasses import dataclass

import requests
from rich.console import Console

console = Console()


@dataclass
class ScriptResult:
    """Kết quả tạo kịch bản"""
    success: bool
    script: str = ""
    error: str = ""


@dataclass
class VoiceResult:
    """Kết quả tạo voice"""
    success: bool
    audio_path: str = ""
    error: str = ""


def create_wav_from_pcm(pcm_data: bytes, output_path: str, sample_rate: int = 24000, channels: int = 1, sample_width: int = 2) -> bool:
    """
    Tạo file WAV từ raw PCM data

    Args:
        pcm_data: Raw PCM audio data
        output_path: Đường dẫn file output
        sample_rate: Sample rate (Hz), Gemini TTS dùng 24000
        channels: Số kênh (1 = mono, 2 = stereo)
        sample_width: Bytes per sample (2 = 16-bit)

    Returns:
        True nếu thành công
    """
    try:
        with wave.open(output_path, 'wb') as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm_data)
        return True
    except Exception as e:
        console.print(f"[red]Lỗi tạo WAV: {e}[/]")
        return False


class GeminiService:
    """Service để tương tác với Google Gemini API"""

    # API endpoints
    GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models"

    # Prompt template cho kịch bản bán hàng vui tươi, nhanh
    SCRIPT_PROMPT_TEMPLATE = """Bạn là MC bán hàng livestream TOP 1, SIÊU VUI VẺ và NĂNG ĐỘNG trên TikTok/Shopee.

THÔNG TIN SẢN PHẨM:
- Tên: {product_name}
- Mô tả: {product_description}

YÊU CẦU:
Viết kịch bản voice-over bán hàng NHANH, VUI TƯƠI, HÀO HỨNG cho video 20-30 giây.

QUY TẮC BẮT BUỘC:
1. Độ dài: 60-100 từ (đọc NHANH VUI trong 20-30 giây)
2. Giọng điệu: VUI VẺ, PHẤN KHÍCH như đang chia sẻ deal HOT cho bạn thân
3. Bắt đầu bằng câu hook hấp dẫn: "Ôi trời ơi!", "Mọi người ơi siêu HOT nè!", "Không mua là phí lắm!"
4. Dùng NHIỀU từ cảm thán: quá đỉnh, siêu xịn, đỉnh của chóp, cực phẩm, xịn sò, mê xỉu, quá trời đẹp
5. Nêu 2-3 ưu điểm nổi bật với sự HÀO HỨNG
6. Tạo cảm giác FOMO: số lượng có hạn, deal cháy hàng, mua ngay kẻo hết
7. Kết thúc mạnh mẽ: "Mua ngay!", "Đặt liền nha!", "Bấm vô giỏ hàng đi mọi người!"

VÍ DỤ GIỌNG ĐIỆU VUI TƯƠI:
"Ôi trời ơi mọi người ơi! Em vừa tìm được món đồ siêu xịn sò nè! Mọi người nhìn đi, chất lượng đỉnh của chóp mà giá thì mềm xèo không tưởng luôn á! Ai mua rồi ai cũng khen nức nở! Hàng về có hạn lắm, shop chỉ còn ít thôi, mua ngay kẻo hết nha mọi người! Bấm vô giỏ hàng liền đi!"

ĐỊNH DẠNG OUTPUT:
Chỉ trả về nội dung kịch bản thuần text, KHÔNG có tiêu đề, KHÔNG có giải thích.

BÂY GIỜ HÃY VIẾT KỊCH BẢN VUI TƯƠI:"""

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        """
        Khởi tạo GeminiService

        Args:
            api_key: Google AI API key
            model: Model để dùng (default: gemini-2.0-flash)
        """
        self.api_key = api_key
        self.model = model
        self.tts_model = "gemini-2.5-flash-preview-tts"

    def generate_script(
        self,
        product_name: str,
        product_description: str,
        custom_prompt: str = None
    ) -> ScriptResult:
        """
        Tạo kịch bản bán hàng từ tên và mô tả sản phẩm

        Args:
            product_name: Tên sản phẩm
            product_description: Mô tả sản phẩm
            custom_prompt: Prompt tùy chỉnh (nếu có)

        Returns:
            ScriptResult với kịch bản hoặc lỗi
        """
        if not self.api_key:
            return ScriptResult(False, error="API key không được cung cấp")

        if not product_name:
            return ScriptResult(False, error="Tên sản phẩm trống")

        # Tạo prompt
        if custom_prompt:
            prompt = custom_prompt.format(
                product_name=product_name,
                product_description=product_description or "Không có mô tả"
            )
        else:
            prompt = self.SCRIPT_PROMPT_TEMPLATE.format(
                product_name=product_name,
                product_description=product_description or "Không có mô tả chi tiết"
            )

        try:
            # Gọi Gemini API với retry
            url = f"{self.GEMINI_API_URL}/{self.model}:generateContent?key={self.api_key}"

            payload = {
                "contents": [{
                    "parts": [{"text": prompt}]
                }],
                "generationConfig": {
                    "temperature": 0.9,
                    "topK": 40,
                    "topP": 0.95,
                    "maxOutputTokens": 200,
                }
            }

            # Retry logic cho rate limit
            max_retries = 3
            for attempt in range(max_retries):
                response = requests.post(
                    url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=30
                )

                if response.status_code == 200:
                    break
                elif response.status_code == 429:  # Rate limit
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 10  # 10s, 20s, 30s
                        console.print(f"[yellow]Rate limit, chờ {wait_time}s...[/]")
                        time.sleep(wait_time)
                        continue
                    else:
                        error_msg = "Đã hết quota API. Vui lòng chờ hoặc kiểm tra billing."
                        return ScriptResult(False, error=error_msg)
                else:
                    break

            if response.status_code != 200:
                error_msg = response.json().get("error", {}).get("message", response.text)
                return ScriptResult(False, error=f"API error: {error_msg}")

            data = response.json()

            # Extract text từ response
            candidates = data.get("candidates", [])
            if not candidates:
                return ScriptResult(False, error="Không có kết quả từ API")

            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            if not parts:
                return ScriptResult(False, error="Response không có nội dung")

            script = parts[0].get("text", "").strip()

            # Clean up script - remove quotes if wrapped
            if script.startswith('"') and script.endswith('"'):
                script = script[1:-1]
            if script.startswith("'") and script.endswith("'"):
                script = script[1:-1]

            if not script:
                return ScriptResult(False, error="Kịch bản trống")

            console.print(f"[green]✓ Đã tạo kịch bản ({len(script)} ký tự)[/]")
            return ScriptResult(True, script=script)

        except requests.RequestException as e:
            return ScriptResult(False, error=f"Lỗi kết nối: {e}")
        except Exception as e:
            return ScriptResult(False, error=f"Lỗi: {e}")

    def generate_voice(
        self,
        text: str,
        output_path: str,
        voice_name: str = "Kore",
        output_format: str = "mp3"
    ) -> VoiceResult:
        """
        Tạo voice từ text sử dụng Gemini TTS

        Args:
            text: Nội dung cần đọc
            output_path: Đường dẫn file output (.mp3 hoặc .wav)
            voice_name: Tên giọng đọc (Aoede, Charon, Fenrir, Kore, Puck)
                        - Kore: Giọng nữ vui tươi, năng động (mặc định)
                        - Puck: Giọng vui vẻ, linh hoạt
                        - Aoede: Giọng nữ trầm ấm
            output_format: Format output (mp3 hoặc wav)

        Returns:
            VoiceResult với đường dẫn file hoặc lỗi
        """
        if not self.api_key:
            return VoiceResult(False, error="API key không được cung cấp")

        if not text:
            return VoiceResult(False, error="Nội dung trống")

        try:
            # Gemini 2.5 Flash TTS API
            url = f"{self.GEMINI_API_URL}/{self.tts_model}:generateContent?key={self.api_key}"

            payload = {
                "contents": [{
                    "parts": [{"text": text}]
                }],
                "generationConfig": {
                    "responseModalities": ["AUDIO"],
                    "speechConfig": {
                        "voiceConfig": {
                            "prebuiltVoiceConfig": {
                                "voiceName": voice_name
                            }
                        }
                    }
                }
            }

            console.print(f"[dim]Đang tạo voice với giọng {voice_name}...[/]")

            response = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=60
            )

            if response.status_code != 200:
                error_data = response.json() if response.text else {}
                error_msg = error_data.get("error", {}).get("message", response.text)
                return VoiceResult(False, error=f"API error: {error_msg}")

            data = response.json()

            # Extract audio data
            candidates = data.get("candidates", [])
            if not candidates:
                return VoiceResult(False, error="Không có kết quả từ API")

            content = candidates[0].get("content", {})
            parts = content.get("parts", [])

            if not parts:
                return VoiceResult(False, error="Response không có audio")

            # Tìm inline_data chứa audio
            audio_data = None
            for part in parts:
                if "inlineData" in part:
                    audio_data = part["inlineData"].get("data")
                    break

            if not audio_data:
                return VoiceResult(False, error="Không tìm thấy audio trong response")

            # Decode base64
            audio_bytes = base64.b64decode(audio_data)

            # Tạo thư mục nếu chưa có
            output_file = Path(output_path)
            # Đảm bảo extension đúng
            if output_format == "mp3" and not str(output_file).endswith(".mp3"):
                output_file = output_file.with_suffix(".mp3")
            output_file.parent.mkdir(parents=True, exist_ok=True)

            # Tạo file WAV từ raw PCM data (Gemini TTS trả về raw PCM 24kHz 16-bit mono)
            tmp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
            if not create_wav_from_pcm(audio_bytes, tmp_wav, sample_rate=24000, channels=1, sample_width=2):
                return VoiceResult(False, error="Không thể tạo file WAV từ dữ liệu audio")

            # Nếu cần MP3, convert từ WAV
            if output_format == "mp3":
                try:
                    # Convert sang MP3 bằng ffmpeg
                    result = subprocess.run(
                        ["ffmpeg", "-y", "-i", tmp_wav, "-acodec", "libmp3lame", "-q:a", "2", str(output_file)],
                        capture_output=True,
                        text=True
                    )
                    if result.returncode != 0:
                        # Nếu ffmpeg fail, giữ lại file WAV
                        console.print(f"[yellow]⚠️ ffmpeg không khả dụng, lưu WAV[/]")
                        output_file = output_file.with_suffix(".wav")
                        shutil.copy(tmp_wav, str(output_file))
                finally:
                    # Xóa file tạm
                    if os.path.exists(tmp_wav):
                        os.unlink(tmp_wav)
            else:
                # Nếu không cần MP3, vẫn convert sang WAV chuẩn
                shutil.move(tmp_wav, str(output_file))

            console.print(f"[green]✓ Đã tạo voice: {output_file.name}[/]")
            return VoiceResult(True, audio_path=str(output_file))

        except requests.RequestException as e:
            return VoiceResult(False, error=f"Lỗi kết nối: {e}")
        except Exception as e:
            return VoiceResult(False, error=f"Lỗi: {e}")

    def create_product_voice(
        self,
        product_code: str,
        product_name: str,
        product_description: str,
        voice_folder: str,
        voice_name: str = "Aoede"
    ) -> Tuple[ScriptResult, VoiceResult]:
        """
        Quy trình đầy đủ: tạo kịch bản -> tạo voice

        Args:
            product_code: Mã sản phẩm (dùng làm tên file)
            product_name: Tên sản phẩm
            product_description: Mô tả sản phẩm
            voice_folder: Thư mục lưu voice
            voice_name: Tên giọng đọc

        Returns:
            Tuple (ScriptResult, VoiceResult)
        """
        # Bước 1: Tạo kịch bản
        console.print(f"[cyan]📝 Đang tạo kịch bản cho {product_code}...[/]")
        script_result = self.generate_script(product_name, product_description)

        if not script_result.success:
            return script_result, VoiceResult(False, error="Chưa có kịch bản")

        console.print(f"[dim]Kịch bản: {script_result.script[:100]}...[/]")

        # Bước 2: Tạo voice (MP3)
        console.print(f"[cyan]🎙️ Đang tạo voice...[/]")
        voice_path = Path(voice_folder) / f"{product_code}.mp3"
        voice_result = self.generate_voice(
            text=script_result.script,
            output_path=str(voice_path),
            voice_name=voice_name,
            output_format="mp3"
        )

        return script_result, voice_result


class ScriptProcessor:
    """Xử lý batch tạo kịch bản và voice từ Google Sheet"""

    def __init__(
        self,
        gemini_service: GeminiService,
        voice_folder: str = "voice",
        name_column: str = "C",
        description_column: str = "D",
        script_column: str = "G",
    ):
        """
        Args:
            gemini_service: GeminiService instance
            voice_folder: Thư mục lưu voice
            name_column: Cột tên sản phẩm
            description_column: Cột mô tả
            script_column: Cột ghi kịch bản
        """
        self.gemini = gemini_service
        self.voice_folder = Path(voice_folder)
        self.name_column = name_column
        self.description_column = description_column
        self.script_column = script_column

        # Tạo thư mục voice nếu chưa có
        self.voice_folder.mkdir(parents=True, exist_ok=True)

    def process_sheet(
        self,
        sheet,  # gspread.Worksheet
        code_column: str = "A",
        skip_existing: bool = True,
        delay_between: float = 1.0,
        voice_name: str = "Aoede",
    ) -> dict:
        """
        Xử lý toàn bộ sheet: tạo kịch bản và voice cho từng sản phẩm

        Args:
            sheet: gspread Worksheet object
            code_column: Cột mã sản phẩm
            skip_existing: Bỏ qua nếu đã có voice
            delay_between: Delay giữa các request
            voice_name: Tên giọng đọc

        Returns:
            Dict với kết quả xử lý
        """
        results = {
            "success": [],
            "failed": [],
            "skipped": []
        }

        try:
            all_values = sheet.get_all_values()

            if not all_values:
                console.print("[yellow]⚠️ Sheet trống[/]")
                return results

            # Tìm index các cột
            code_col_idx = ord(code_column.upper()) - ord('A')
            name_col_idx = ord(self.name_column.upper()) - ord('A')
            desc_col_idx = ord(self.description_column.upper()) - ord('A')
            script_col_idx = ord(self.script_column.upper()) - ord('A')

            # Bỏ qua header
            data_rows = all_values[1:] if len(all_values) > 1 else []

            console.print(f"[cyan]📋 Tìm thấy {len(data_rows)} dòng dữ liệu[/]")

            for row_idx, row in enumerate(data_rows, start=2):
                # Lấy thông tin
                code = row[code_col_idx].strip() if len(row) > code_col_idx else ""
                name = row[name_col_idx].strip() if len(row) > name_col_idx else ""
                description = row[desc_col_idx].strip() if len(row) > desc_col_idx else ""
                existing_script = row[script_col_idx].strip() if len(row) > script_col_idx else ""

                if not code or not name:
                    continue

                # Kiểm tra đã có voice chưa (check cả .mp3 và .wav)
                voice_path_mp3 = self.voice_folder / f"{code}.mp3"
                voice_path_wav = self.voice_folder / f"{code}.wav"
                voice_exists = voice_path_mp3.exists() or voice_path_wav.exists()

                if skip_existing and voice_exists:
                    console.print(f"[dim]⏭️ {code}: đã có voice[/]")
                    results["skipped"].append(code)
                    continue

                # Kiểm tra đã có script trong sheet chưa
                if skip_existing and existing_script:
                    console.print(f"[dim]⏭️ {code}: đã có kịch bản[/]")
                    # Nếu có script nhưng chưa có voice -> tạo voice
                    if not voice_exists:
                        console.print(f"[cyan]🎙️ Tạo voice từ kịch bản có sẵn...[/]")
                        voice_result = self.gemini.generate_voice(
                            text=existing_script,
                            output_path=str(voice_path_mp3),
                            voice_name=voice_name,
                            output_format="mp3"
                        )
                        if voice_result.success:
                            results["success"].append(code)
                        else:
                            results["failed"].append((code, voice_result.error))
                    else:
                        results["skipped"].append(code)
                    continue

                console.print(f"\n[bold]📦 [{row_idx}] {code}[/]")
                console.print(f"[dim]Tên: {name[:50]}...[/]" if len(name) > 50 else f"[dim]Tên: {name}[/]")

                # Tạo kịch bản và voice
                script_result, voice_result = self.gemini.create_product_voice(
                    product_code=code,
                    product_name=name,
                    product_description=description,
                    voice_folder=str(self.voice_folder),
                    voice_name=voice_name
                )

                # Ghi kịch bản vào sheet
                if script_result.success:
                    try:
                        cell = f"{self.script_column}{row_idx}"
                        sheet.update_acell(cell, script_result.script)
                        console.print(f"[green]✓ Đã ghi kịch bản vào {cell}[/]")
                    except Exception as e:
                        console.print(f"[yellow]⚠️ Lỗi ghi sheet: {e}[/]")

                if voice_result.success:
                    results["success"].append(code)
                else:
                    results["failed"].append((code, voice_result.error))

                # Delay
                if delay_between > 0:
                    time.sleep(delay_between)

            return results

        except Exception as e:
            console.print(f"[red]❌ Lỗi: {e}[/]")
            return results


def create_voice_for_product(
    api_key: str,
    product_code: str,
    product_name: str,
    product_description: str,
    voice_folder: str = "voice",
    voice_name: str = "Aoede"
) -> Tuple[ScriptResult, VoiceResult]:
    """
    Utility function để tạo voice cho 1 sản phẩm

    Args:
        api_key: Gemini API key
        product_code: Mã sản phẩm
        product_name: Tên sản phẩm
        product_description: Mô tả
        voice_folder: Thư mục lưu voice
        voice_name: Tên giọng đọc

    Returns:
        Tuple (ScriptResult, VoiceResult)
    """
    service = GeminiService(api_key)
    return service.create_product_voice(
        product_code=product_code,
        product_name=product_name,
        product_description=product_description,
        voice_folder=voice_folder,
        voice_name=voice_name
    )
