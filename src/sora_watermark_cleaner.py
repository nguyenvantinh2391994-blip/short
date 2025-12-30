"""
Sora Watermark Cleaner - Xóa logo Sora khỏi video

Wrapper cho SoraWatermarkCleaner (https://github.com/linkedlist771/SoraWatermarkCleaner)
Sử dụng YOLO để phát hiện và LAMA/E2FGVI để xóa watermark.

Cài đặt:
    pip install git+https://github.com/linkedlist771/SoraWatermarkCleaner.git

    Hoặc clone và cài:
    git clone https://github.com/linkedlist771/SoraWatermarkCleaner.git
    cd SoraWatermarkCleaner
    uv sync  # hoặc pip install -e .

Yêu cầu:
    - Python >= 3.12
    - FFmpeg
    - GPU với CUDA (khuyến nghị)
"""

import subprocess
import sys
from pathlib import Path
from typing import Optional, List, Callable
from dataclasses import dataclass

try:
    from rich.console import Console
    console = Console()
except ImportError:
    # Fallback nếu không có rich
    class FakeConsole:
        def print(self, msg):
            # Strip rich markup
            import re
            clean = re.sub(r'\[/?[a-z_]+\]', '', str(msg))
            print(clean)
    console = FakeConsole()


@dataclass
class CleanResult:
    """Kết quả xóa watermark"""
    success: bool
    input_path: str = ""
    output_path: str = ""
    error: str = ""


def check_sorawm_installed() -> bool:
    """Kiểm tra SoraWM đã được cài đặt chưa"""
    try:
        from sorawm.core import SoraWM
        from sorawm.schemas import CleanerType
        return True
    except ImportError:
        return False


def install_sorawm() -> bool:
    """Cài đặt SoraWM từ GitHub"""
    try:
        console.print("[yellow]Đang cài đặt SoraWatermarkCleaner từ GitHub...[/]")
        console.print("[yellow]Quá trình này có thể mất vài phút...[/]")

        # Cài từ GitHub
        subprocess.check_call([
            sys.executable, "-m", "pip", "install",
            "git+https://github.com/linkedlist771/SoraWatermarkCleaner.git",
            "--quiet"
        ])

        console.print("[green]✓ Đã cài đặt SoraWatermarkCleaner thành công[/]")
        return True
    except subprocess.CalledProcessError as e:
        console.print(f"[red]✗ Lỗi cài đặt: {e}[/]")
        console.print("[yellow]Thử cài thủ công:[/]")
        console.print("  git clone https://github.com/linkedlist771/SoraWatermarkCleaner.git")
        console.print("  cd SoraWatermarkCleaner")
        console.print("  pip install -e .")
        return False


class SoraWatermarkRemover:
    """
    Xóa watermark Sora từ video.

    Sử dụng 2 model:
    - LAMA: Nhanh, chất lượng tốt (khuyến nghị)
    - E2FGVI_HQ: Chậm hơn nhưng giữ temporal consistency (cần GPU mạnh)
    """

    def __init__(
        self,
        cleaner_type: str = "lama",  # "lama" hoặc "e2fgvi_hq"
        enable_torch_compile: bool = False,
        on_log: Optional[Callable[[str], None]] = None
    ):
        """
        Args:
            cleaner_type: Loại cleaner ("lama" hoặc "e2fgvi_hq")
            enable_torch_compile: Bật torch compile cho E2FGVI_HQ (nhanh hơn nhưng mất temporal consistency)
            on_log: Callback để log
        """
        self.cleaner_type = cleaner_type.lower()
        self.enable_torch_compile = enable_torch_compile
        self.on_log = on_log
        self._sora_wm = None
        self._initialized = False

    def log(self, msg: str):
        """Log message"""
        if self.on_log:
            self.on_log(msg)
        else:
            console.print(msg)

    def setup(self) -> bool:
        """Khởi tạo SoraWM"""
        if self._initialized:
            return True

        if not check_sorawm_installed():
            self.log("[yellow]SoraWatermarkCleaner chưa được cài đặt.[/]")
            if not install_sorawm():
                return False

        try:
            from sorawm.core import SoraWM
            from sorawm.schemas import CleanerType

            if self.cleaner_type == "e2fgvi_hq":
                cleaner = CleanerType.E2FGVI_HQ
                self.log("   Dùng E2FGVI_HQ (temporal consistency, chậm)")
            else:
                cleaner = CleanerType.LAMA
                self.log("   Dùng LAMA (nhanh, chất lượng tốt)")

            self._sora_wm = SoraWM(
                cleaner_type=cleaner,
                enable_torch_compile=self.enable_torch_compile
            )
            self._initialized = True
            self.log("[green]✓ SoraWM đã sẵn sàng[/]")
            return True

        except Exception as e:
            self.log(f"[red]✗ Lỗi khởi tạo SoraWM: {e}[/]")
            import traceback
            traceback.print_exc()
            return False

    def clean_video(
        self,
        input_path: str,
        output_path: str = None
    ) -> CleanResult:
        """
        Xóa watermark từ 1 video.

        Args:
            input_path: Đường dẫn video input
            output_path: Đường dẫn video output (mặc định: thêm _clean trước .mp4)

        Returns:
            CleanResult với thông tin kết quả
        """
        input_path = Path(input_path)

        if not input_path.exists():
            return CleanResult(False, str(input_path), error=f"File không tồn tại: {input_path}")

        # Tạo output path nếu chưa có
        if not output_path:
            output_path = input_path.parent / f"{input_path.stem}_clean{input_path.suffix}"
        output_path = Path(output_path)

        # Đảm bảo thư mục output tồn tại
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            if not self._initialized:
                if not self.setup():
                    return CleanResult(False, str(input_path), error="Không thể khởi tạo SoraWM")

            self.log(f"   Đang xử lý: {input_path.name}")

            # Chạy SoraWM
            self._sora_wm.run(input_path, output_path)

            if output_path.exists() and output_path.stat().st_size > 1000:
                self.log(f"[green]   ✓ Đã xóa logo: {output_path.name}[/]")
                return CleanResult(True, str(input_path), str(output_path))
            else:
                return CleanResult(False, str(input_path), error="Output không được tạo hoặc file rỗng")

        except Exception as e:
            self.log(f"[red]   ✗ Lỗi: {e}[/]")
            import traceback
            traceback.print_exc()
            return CleanResult(False, str(input_path), error=str(e))

    def clean_folder(
        self,
        input_folder: str,
        output_folder: str = None,
        pattern: str = "*.mp4",
        skip_existing: bool = True
    ) -> List[CleanResult]:
        """
        Xóa watermark từ tất cả video trong thư mục.

        Args:
            input_folder: Thư mục chứa video
            output_folder: Thư mục output (mặc định: cùng thư mục, thêm _clean)
            pattern: Pattern để tìm file (default: *.mp4)
            skip_existing: Bỏ qua nếu đã có file _clean

        Returns:
            List các CleanResult
        """
        input_folder = Path(input_folder)
        results = []

        if not input_folder.exists():
            self.log(f"[red]Thư mục không tồn tại: {input_folder}[/]")
            return results

        # Tìm tất cả video
        videos = list(input_folder.glob(pattern))

        # Lọc bỏ các file đã clean
        videos = [v for v in videos if "_clean" not in v.stem]

        if not videos:
            self.log(f"[yellow]Không tìm thấy video trong {input_folder}[/]")
            return results

        self.log(f"Tìm thấy {len(videos)} video cần xử lý")

        for video in videos:
            if output_folder:
                output_path = Path(output_folder) / f"{video.stem}_clean{video.suffix}"
            else:
                output_path = video.parent / f"{video.stem}_clean{video.suffix}"

            # Skip nếu đã tồn tại
            if skip_existing and output_path.exists():
                self.log(f"   ⏭️ Bỏ qua (đã có): {video.name}")
                continue

            result = self.clean_video(str(video), str(output_path))
            results.append(result)

        success_count = sum(1 for r in results if r.success)
        self.log(f"\n✅ Hoàn thành: {success_count}/{len(results)} video")

        return results


def clean_sora_videos(
    input_folder: str,
    cleaner_type: str = "lama",
    on_log: Optional[Callable[[str], None]] = None
) -> List[CleanResult]:
    """
    Utility function để xóa watermark từ tất cả video SORA trong thư mục.

    Tìm các file có pattern: 00_sora_*.mp4 hoặc *_sora_*.mp4

    Args:
        input_folder: Thư mục chứa các thư mục mã sản phẩm
        cleaner_type: "lama" hoặc "e2fgvi_hq"
        on_log: Callback để log

    Returns:
        List các CleanResult
    """
    input_folder = Path(input_folder)
    remover = SoraWatermarkRemover(cleaner_type=cleaner_type, on_log=on_log)

    all_results = []

    # Duyệt qua các thư mục con (mã sản phẩm)
    for code_folder in input_folder.iterdir():
        if not code_folder.is_dir():
            continue

        video_folder = code_folder / "video"
        if not video_folder.exists():
            continue

        # Tìm video SORA
        sora_videos = list(video_folder.glob("*sora*.mp4"))
        sora_videos = [v for v in sora_videos if "_clean" not in v.stem]

        for video in sora_videos:
            output_path = video.parent / f"{video.stem}_clean{video.suffix}"

            if output_path.exists():
                if on_log:
                    on_log(f"   ⏭️ Bỏ qua (đã có): {video.name}")
                continue

            result = remover.clean_video(str(video), str(output_path))
            all_results.append(result)

    return all_results


# CLI interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Xóa watermark Sora từ video",
        epilog="""
Ví dụ:
    python sora_watermark_cleaner.py video.mp4
    python sora_watermark_cleaner.py video.mp4 -o output.mp4
    python sora_watermark_cleaner.py ./videos/ --pattern "*.mp4"
    python sora_watermark_cleaner.py video.mp4 -m e2fgvi_hq  # chất lượng cao hơn
        """
    )
    parser.add_argument("input", help="File video hoặc thư mục")
    parser.add_argument("-o", "--output", help="Output path")
    parser.add_argument("-m", "--model", default="lama", choices=["lama", "e2fgvi_hq"],
                       help="Model để dùng (default: lama)")
    parser.add_argument("--pattern", default="*.mp4", help="Pattern cho batch processing")
    parser.add_argument("--install", action="store_true", help="Chỉ cài đặt SoraWM")

    args = parser.parse_args()

    if args.install:
        if check_sorawm_installed():
            console.print("[green]✓ SoraWM đã được cài đặt[/]")
        else:
            install_sorawm()
        sys.exit(0)

    input_path = Path(args.input)

    if input_path.is_file():
        # Xử lý 1 file
        remover = SoraWatermarkRemover(cleaner_type=args.model)
        result = remover.clean_video(args.input, args.output)
        if result.success:
            console.print(f"[green]✓ Đã xóa logo: {result.output_path}[/]")
        else:
            console.print(f"[red]✗ Lỗi: {result.error}[/]")
            sys.exit(1)
    elif input_path.is_dir():
        # Batch processing
        remover = SoraWatermarkRemover(cleaner_type=args.model)
        results = remover.clean_folder(args.input, args.output, args.pattern)

        success = sum(1 for r in results if r.success)
        console.print(f"\n[green]Hoàn thành: {success}/{len(results)} video[/]")
        if success < len(results):
            sys.exit(1)
    else:
        console.print(f"[red]Không tìm thấy: {input_path}[/]")
        sys.exit(1)
