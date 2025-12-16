"""
Video Generator - Tạo video short từ ảnh sản phẩm
Hỗ trợ 2 mode:
1. Grok AI: Dùng API Grok để tạo video AI
2. FFmpeg: Ghép ảnh thành video với hiệu ứng (fallback)
"""

import os
import json
import subprocess
from pathlib import Path
from typing import List, Optional, Dict, Tuple
from dataclasses import dataclass
from datetime import datetime
from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn

from .sheets_reader import Product
from .grok_client import GrokClient, create_product_video_prompt

console = Console()


@dataclass
class VideoConfig:
    """Cấu hình video"""
    width: int = 1080
    height: int = 1920  # 9:16 cho TikTok/Reels
    fps: int = 30
    duration_per_image: float = 3.0  # Giây mỗi ảnh
    transition_duration: float = 0.5  # Giây chuyển cảnh
    output_format: str = "mp4"
    codec: str = "libx264"
    audio_codec: str = "aac"
    quality: int = 23  # CRF (lower = better, 18-28 recommended)


class VideoGenerator:
    """Tạo video từ ảnh sản phẩm"""

    def __init__(
        self,
        products_dir: str = "products",
        output_dir: str = "outputs",
        music_dir: str = "music",
        config: Optional[VideoConfig] = None
    ):
        self.products_dir = Path(products_dir)
        self.output_dir = Path(output_dir)
        self.music_dir = Path(music_dir)
        self.config = config or VideoConfig()

        # Tạo thư mục nếu chưa có
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Grok client (optional)
        self.grok_client: Optional[GrokClient] = None

    def init_grok(self, tokens_file: str = "config/grok_tokens.json") -> bool:
        """Khởi tạo Grok client"""
        try:
            self.grok_client = GrokClient(tokens_file)
            return True
        except Exception as e:
            console.print(f"[yellow]⚠️ Không thể khởi tạo Grok: {e}[/]")
            return False

    def get_product_images(self, product: Product) -> List[Path]:
        """Lấy danh sách ảnh của sản phẩm"""
        # Thư mục ảnh: products/{product_id}/ hoặc custom folder
        if product.images_folder:
            folder = Path(product.images_folder)
            if not folder.is_absolute():
                folder = self.products_dir / product.images_folder
        else:
            folder = self.products_dir / product.id

        if not folder.exists():
            console.print(f"[yellow]⚠️ Không tìm thấy thư mục ảnh: {folder}[/]")
            return []

        # Tìm các file ảnh
        image_extensions = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
        images = []

        for file in sorted(folder.iterdir()):
            if file.suffix.lower() in image_extensions:
                images.append(file)

        return images

    def get_music_file(self, category: Optional[str] = None) -> Optional[Path]:
        """Lấy file nhạc nền"""
        if not self.music_dir.exists():
            return None

        music_files = list(self.music_dir.glob("*.mp3")) + list(self.music_dir.glob("*.wav"))

        if not music_files:
            return None

        # TODO: Chọn nhạc theo category
        # Hiện tại chọn file đầu tiên
        return music_files[0]

    def generate_with_grok(
        self,
        product: Product,
        images: List[Path],
        output_path: Optional[Path] = None
    ) -> Optional[Path]:
        """Tạo video bằng Grok AI"""
        if not self.grok_client:
            console.print("[red]❌ Grok client chưa được khởi tạo[/]")
            return None

        # Tạo prompt
        prompt = create_product_video_prompt(
            product_name=product.name,
            price=product.price,
            description=product.description or "",
            promotion=product.promotion or "",
        )

        console.print(f"[cyan]Prompt:[/] {prompt[:100]}...")

        # Gọi API Grok
        response = self.grok_client.generate_video_from_images(
            image_paths=[str(img) for img in images],
            prompt=prompt,
            duration=int(len(images) * self.config.duration_per_image)
        )

        if not response.success:
            console.print(f"[red]❌ Grok error: {response.error}[/]")
            return None

        # Download video
        if response.video_url:
            if output_path is None:
                output_path = self.output_dir / f"{product.id}_grok.{self.config.output_format}"

            if self.grok_client.download_media(response.video_url, str(output_path)):
                return output_path

        return None

    def generate_with_ffmpeg(
        self,
        product: Product,
        images: List[Path],
        output_path: Optional[Path] = None,
        music_file: Optional[Path] = None
    ) -> Optional[Path]:
        """Tạo video bằng FFmpeg (local)"""
        if not images:
            console.print("[red]❌ Không có ảnh để tạo video[/]")
            return None

        if not self._check_ffmpeg():
            console.print("[red]❌ FFmpeg chưa được cài đặt[/]")
            console.print("[yellow]Cài đặt: https://ffmpeg.org/download.html[/]")
            return None

        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = self.output_dir / f"{product.id}_{timestamp}.{self.config.output_format}"

        # Tạo file danh sách ảnh cho FFmpeg
        concat_file = self.output_dir / f"temp_{product.id}_concat.txt"
        self._create_concat_file(images, concat_file)

        try:
            with Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
                console=console,
            ) as progress:
                task = progress.add_task(f"Tạo video {product.id}...", total=100)

                # Bước 1: Scale và pad ảnh (30%)
                progress.update(task, completed=10, description="Chuẩn bị ảnh...")
                scaled_images = self._prepare_images(images, product.id)

                # Bước 2: Tạo video từ ảnh (50%)
                progress.update(task, completed=30, description="Tạo video...")
                temp_video = self.output_dir / f"temp_{product.id}_video.mp4"
                self._create_slideshow(scaled_images, temp_video)

                # Bước 3: Thêm text overlay (70%)
                progress.update(task, completed=50, description="Thêm text...")
                temp_with_text = self.output_dir / f"temp_{product.id}_text.mp4"
                self._add_text_overlay(temp_video, temp_with_text, product)

                # Bước 4: Thêm nhạc nền (90%)
                progress.update(task, completed=70, description="Thêm nhạc...")
                if music_file and music_file.exists():
                    self._add_audio(temp_with_text, music_file, output_path)
                else:
                    # Copy video không có nhạc
                    temp_with_text.rename(output_path)

                progress.update(task, completed=100, description="Hoàn thành!")

            # Dọn dẹp temp files
            self._cleanup_temp_files(product.id)

            console.print(f"[green]✅ Đã tạo video: {output_path}[/]")
            return output_path

        except Exception as e:
            console.print(f"[red]❌ Lỗi tạo video: {e}[/]")
            self._cleanup_temp_files(product.id)
            return None
        finally:
            if concat_file.exists():
                concat_file.unlink()

    def _check_ffmpeg(self) -> bool:
        """Kiểm tra FFmpeg đã cài đặt chưa"""
        try:
            subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                check=True
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def _create_concat_file(self, images: List[Path], output: Path) -> None:
        """Tạo file concat cho FFmpeg"""
        with open(output, "w", encoding="utf-8") as f:
            for img in images:
                # Escape đường dẫn
                escaped_path = str(img.absolute()).replace("'", "'\\''")
                f.write(f"file '{escaped_path}'\n")
                f.write(f"duration {self.config.duration_per_image}\n")
            # Thêm ảnh cuối một lần nữa (required by FFmpeg concat)
            if images:
                escaped_path = str(images[-1].absolute()).replace("'", "'\\''")
                f.write(f"file '{escaped_path}'\n")

    def _prepare_images(self, images: List[Path], product_id: str) -> List[Path]:
        """Scale và pad ảnh về đúng kích thước"""
        scaled_images = []
        w, h = self.config.width, self.config.height

        for i, img in enumerate(images):
            output = self.output_dir / f"temp_{product_id}_img_{i:03d}.jpg"

            cmd = [
                "ffmpeg", "-y", "-i", str(img),
                "-vf", f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black",
                "-q:v", "2",
                str(output)
            ]

            subprocess.run(cmd, capture_output=True, check=True)
            scaled_images.append(output)

        return scaled_images

    def _create_slideshow(self, images: List[Path], output: Path) -> None:
        """Tạo slideshow từ ảnh với hiệu ứng chuyển cảnh"""
        if not images:
            return

        # Sử dụng xfade filter cho hiệu ứng chuyển cảnh
        inputs = []
        filter_complex = []

        for i, img in enumerate(images):
            inputs.extend(["-loop", "1", "-t", str(self.config.duration_per_image), "-i", str(img)])

        # Tạo filter chain cho xfade
        if len(images) > 1:
            # Xfade giữa các ảnh
            filter_parts = []
            for i in range(len(images) - 1):
                if i == 0:
                    filter_parts.append(
                        f"[0:v][1:v]xfade=transition=fade:duration={self.config.transition_duration}:offset={self.config.duration_per_image - self.config.transition_duration}[v1]"
                    )
                else:
                    prev = f"v{i}"
                    next_idx = i + 1
                    out = f"v{next_idx}"
                    offset = (i + 1) * self.config.duration_per_image - (i + 1) * self.config.transition_duration
                    filter_parts.append(
                        f"[{prev}][{next_idx}:v]xfade=transition=fade:duration={self.config.transition_duration}:offset={offset}[{out}]"
                    )

            filter_complex = ";".join(filter_parts)
            last_output = f"[v{len(images)-1}]"

            cmd = [
                "ffmpeg", "-y",
                *inputs,
                "-filter_complex", filter_complex,
                "-map", last_output,
                "-c:v", self.config.codec,
                "-pix_fmt", "yuv420p",
                "-crf", str(self.config.quality),
                "-r", str(self.config.fps),
                str(output)
            ]
        else:
            # Chỉ có 1 ảnh
            cmd = [
                "ffmpeg", "-y",
                "-loop", "1", "-t", str(self.config.duration_per_image),
                "-i", str(images[0]),
                "-c:v", self.config.codec,
                "-pix_fmt", "yuv420p",
                "-crf", str(self.config.quality),
                "-r", str(self.config.fps),
                str(output)
            ]

        subprocess.run(cmd, capture_output=True, check=True)

    def _add_text_overlay(self, input_video: Path, output: Path, product: Product) -> None:
        """Thêm text overlay (tên SP, giá, khuyến mãi)"""
        # Tạo filter cho text
        filters = []

        # Font settings
        font_size = 48
        font_color = "white"
        box_color = "black@0.5"

        # Tên sản phẩm (top)
        name_text = product.name.replace("'", "\\'")[:50]
        filters.append(
            f"drawtext=text='{name_text}':fontsize={font_size}:fontcolor={font_color}:"
            f"x=(w-text_w)/2:y=100:box=1:boxcolor={box_color}:boxborderw=10"
        )

        # Giá (bottom)
        price_text = product.price.replace("'", "\\'")
        filters.append(
            f"drawtext=text='{price_text}':fontsize={font_size + 12}:fontcolor=yellow:"
            f"x=(w-text_w)/2:y=h-200:box=1:boxcolor={box_color}:boxborderw=10"
        )

        # Khuyến mãi (nếu có)
        if product.promotion:
            promo_text = product.promotion.replace("'", "\\'")[:30]
            filters.append(
                f"drawtext=text='{promo_text}':fontsize={font_size - 8}:fontcolor=red:"
                f"x=(w-text_w)/2:y=h-120:box=1:boxcolor=white@0.8:boxborderw=5"
            )

        filter_str = ",".join(filters)

        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_video),
            "-vf", filter_str,
            "-c:v", self.config.codec,
            "-crf", str(self.config.quality),
            "-c:a", "copy",
            str(output)
        ]

        subprocess.run(cmd, capture_output=True, check=True)

    def _add_audio(self, input_video: Path, audio: Path, output: Path) -> None:
        """Thêm nhạc nền"""
        # Lấy độ dài video
        probe_cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(input_video)
        ]
        result = subprocess.run(probe_cmd, capture_output=True, text=True)
        duration = float(result.stdout.strip())

        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_video),
            "-i", str(audio),
            "-c:v", "copy",
            "-c:a", self.config.audio_codec,
            "-shortest",
            "-t", str(duration),
            "-af", "afade=t=out:st=" + str(duration - 1) + ":d=1",  # Fade out 1s cuối
            str(output)
        ]

        subprocess.run(cmd, capture_output=True, check=True)

    def _cleanup_temp_files(self, product_id: str) -> None:
        """Xóa các file tạm"""
        for temp_file in self.output_dir.glob(f"temp_{product_id}_*"):
            try:
                temp_file.unlink()
            except:
                pass

    def generate_video(
        self,
        product: Product,
        use_grok: bool = False,
        output_path: Optional[Path] = None
    ) -> Optional[Path]:
        """Tạo video cho sản phẩm (entry point chính)"""
        console.print(f"\n[bold cyan]Tạo video cho: {product.name}[/]")
        console.print(f"[dim]ID: {product.id} | Giá: {product.price}[/]")

        # Lấy ảnh sản phẩm
        images = self.get_product_images(product)
        if not images:
            console.print(f"[red]❌ Không tìm thấy ảnh cho sản phẩm {product.id}[/]")
            return None

        console.print(f"[green]Tìm thấy {len(images)} ảnh[/]")

        # Lấy nhạc nền
        music = self.get_music_file(product.category)
        if music:
            console.print(f"[green]Nhạc nền: {music.name}[/]")

        # Tạo video
        if use_grok and self.grok_client:
            result = self.generate_with_grok(product, images, output_path)
            if result:
                return result
            console.print("[yellow]⚠️ Grok thất bại, chuyển sang FFmpeg...[/]")

        # Fallback to FFmpeg
        return self.generate_with_ffmpeg(product, images, output_path, music)

    def generate_batch(
        self,
        products: List[Product],
        use_grok: bool = False
    ) -> Dict[str, Optional[Path]]:
        """Tạo video hàng loạt"""
        results = {}

        console.print(f"\n[bold]Bắt đầu tạo {len(products)} video...[/]\n")

        for i, product in enumerate(products, 1):
            console.print(f"[dim]({i}/{len(products)})[/]")
            result = self.generate_video(product, use_grok)
            results[product.id] = result

        # Summary
        success = sum(1 for v in results.values() if v is not None)
        console.print(f"\n[bold]Kết quả: {success}/{len(products)} video thành công[/]")

        return results
