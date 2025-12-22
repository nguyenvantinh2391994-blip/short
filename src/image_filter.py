"""
Image Filter - Lọc ảnh sản phẩm
- Chỉ giữ ảnh có người (thật)
- Loại bỏ ảnh ghép/collage (ảnh nhiều ảnh nhỏ ghép lại)
"""

import cv2
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional
from dataclasses import dataclass

try:
    import mediapipe as mp
    HAS_MEDIAPIPE = True
except ImportError:
    HAS_MEDIAPIPE = False

from rich.console import Console

console = Console()


@dataclass
class ImageFilterResult:
    """Kết quả lọc ảnh"""
    path: str
    has_person: bool
    is_collage: bool
    should_keep: bool
    reason: str = ""


class ImageFilter:
    """Bộ lọc ảnh sản phẩm - ĐƠN GIẢN VÀ CHÍNH XÁC"""

    def __init__(
        self,
        require_person: bool = True,
        reject_collage: bool = True,
        min_person_confidence: float = 0.5,
    ):
        self.require_person = require_person
        self.reject_collage = reject_collage
        self.min_person_confidence = min_person_confidence

        # Khởi tạo mediapipe pose detector
        self._pose = None
        self._face_cascade = None

        if HAS_MEDIAPIPE:
            try:
                self.mp_pose = mp.solutions.pose
                self._pose = self.mp_pose.Pose(
                    static_image_mode=True,
                    model_complexity=1,
                    min_detection_confidence=min_person_confidence
                )
            except Exception as e:
                console.print(f"[yellow]Không khởi tạo được MediaPipe Pose: {e}[/]")

        # Fallback: OpenCV face detection
        try:
            cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            self._face_cascade = cv2.CascadeClassifier(cascade_path)
        except Exception as e:
            console.print(f"[yellow]Không load được face cascade: {e}[/]")

    def detect_person(self, image: np.ndarray) -> Tuple[bool, float]:
        """Phát hiện người trong ảnh"""
        if image is None:
            return False, 0.0

        # Thử MediaPipe Pose trước
        if self._pose is not None:
            try:
                rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                results = self._pose.process(rgb_image)

                if results.pose_landmarks:
                    visibilities = [lm.visibility for lm in results.pose_landmarks.landmark]
                    avg_visibility = sum(visibilities) / len(visibilities)
                    return True, avg_visibility
            except Exception:
                pass

        # Fallback: OpenCV face detection
        if self._face_cascade is not None:
            try:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                faces = self._face_cascade.detectMultiScale(
                    gray,
                    scaleFactor=1.1,
                    minNeighbors=5,
                    minSize=(30, 30)
                )

                if len(faces) > 0:
                    max_area = max(w * h for (x, y, w, h) in faces)
                    img_area = image.shape[0] * image.shape[1]
                    confidence = min(max_area / img_area * 10, 1.0)
                    return True, confidence
            except Exception:
                pass

        return False, 0.0

    def detect_collage(self, image: np.ndarray) -> Tuple[bool, float]:
        """
        Phát hiện ảnh ghép/collage - CHỈ phát hiện các trường hợp RÕ RÀNG:
        1. Có đường viền/border rõ ràng chia ảnh
        2. Có >= 3 khuôn mặt xếp thành hàng đều
        """
        if image is None:
            return False, 0.0

        try:
            h, w = image.shape[:2]

            # === 1. Phát hiện ĐƯỜNG VIỀN THẲNG chia ảnh ===
            # Chỉ check các vị trí chia đều: 1/2, 1/3, 2/3
            border_score = self._detect_clear_border(image)
            if border_score > 0.7:
                return True, border_score

            # === 2. Phát hiện NHIỀU MẶT xếp hàng đều ===
            face_grid_score = self._detect_face_grid_strict(image)
            if face_grid_score > 0.7:
                return True, face_grid_score

            return False, 0.0

        except Exception as e:
            console.print(f"[dim]Collage detection error: {e}[/]")
            return False, 0.0

    def _detect_clear_border(self, image: np.ndarray) -> float:
        """
        Phát hiện đường viền RÕ RÀNG chia ảnh
        - Viền phải là đường thẳng dọc, màu đồng nhất
        - Viền phải chia ảnh thành các phần có nội dung khác nhau
        """
        h, w = image.shape[:2]

        # Chỉ check các vị trí chia đều
        check_positions = [w // 2, w // 3, 2 * w // 3]

        for pos in check_positions:
            if pos <= 30 or pos >= w - 30:
                continue

            # Lấy strip dọc tại vị trí này (rộng 6px)
            strip = image[:, pos-3:pos+3]

            # Kiểm tra strip có màu đồng nhất không (std thấp)
            strip_std = np.std(strip, axis=(0, 1))
            avg_strip_std = np.mean(strip_std)

            # Viền phải có màu đồng nhất (std < 25)
            if avg_strip_std > 25:
                continue

            # Lấy 2 vùng bên cạnh
            left_region = image[:, max(0, pos-50):pos-10]
            right_region = image[:, pos+10:min(w, pos+50)]

            if left_region.size == 0 or right_region.size == 0:
                continue

            # So sánh màu trung bình của viền với 2 bên
            strip_mean = np.mean(strip, axis=(0, 1))
            left_mean = np.mean(left_region, axis=(0, 1))
            right_mean = np.mean(right_region, axis=(0, 1))

            # Viền phải khác màu với cả 2 bên
            diff_left = np.linalg.norm(strip_mean - left_mean)
            diff_right = np.linalg.norm(strip_mean - right_mean)

            # VÀ 2 bên phải khác nhau
            diff_sides = np.linalg.norm(left_mean - right_mean)

            # Điều kiện: viền khác 2 bên (> 30) VÀ 2 bên khác nhau (> 40)
            if diff_left > 30 and diff_right > 30 and diff_sides > 40:
                console.print(f"[dim]Found border at x={pos}: strip_std={avg_strip_std:.1f}, diff_sides={diff_sides:.1f}[/]")
                return 0.9

        return 0.0

    def _detect_face_grid_strict(self, image: np.ndarray) -> float:
        """
        Phát hiện >= 3 khuôn mặt xếp thành hàng đều
        Đây là dấu hiệu RÕ RÀNG của ảnh ghép (nhiều outfit của 1 model)
        """
        if self._face_cascade is None:
            return 0.0

        try:
            h, w = image.shape[:2]
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            faces = self._face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=4,
                minSize=(25, 25)
            )

            # Cần ít nhất 3 mặt
            if len(faces) < 3:
                return 0.0

            # Lấy tâm X của các mặt
            face_centers_x = sorted([(x + fw // 2) for x, y, fw, fh in faces])

            # Tính khoảng cách giữa các mặt liền kề
            gaps = []
            for i in range(len(face_centers_x) - 1):
                gaps.append(face_centers_x[i + 1] - face_centers_x[i])

            if len(gaps) < 2:
                return 0.0

            # Kiểm tra các gap có gần bằng nhau không
            avg_gap = sum(gaps) / len(gaps)
            max_deviation = max(abs(g - avg_gap) for g in gaps)

            # Nếu gap đều nhau (deviation < 20% của avg)
            if max_deviation < avg_gap * 0.25:
                # Và gap gần với chia đều ảnh
                expected_gap = w / (len(faces) + 1)
                if abs(avg_gap - expected_gap) < expected_gap * 0.4:
                    console.print(f"[dim]Found face grid: {len(faces)} faces, gaps={gaps}[/]")
                    return 0.9

            return 0.0

        except Exception:
            return 0.0

    def filter_image(self, image_path: str) -> ImageFilterResult:
        """Lọc một ảnh"""
        path = Path(image_path)

        if not path.exists():
            return ImageFilterResult(
                path=str(path),
                has_person=False,
                is_collage=False,
                should_keep=False,
                reason="File không tồn tại"
            )

        image = cv2.imread(str(path))
        if image is None:
            return ImageFilterResult(
                path=str(path),
                has_person=False,
                is_collage=False,
                should_keep=False,
                reason="Không đọc được ảnh"
            )

        # Detect person
        has_person, person_conf = self.detect_person(image)

        # Detect collage (chỉ khi reject_collage = True)
        is_collage = False
        collage_conf = 0.0
        if self.reject_collage:
            is_collage, collage_conf = self.detect_collage(image)

        # Quyết định giữ hay bỏ
        should_keep = True
        reason = ""

        # Logic đơn giản:
        # 1. Nếu là collage -> BỎ
        # 2. Nếu không có người VÀ require_person -> BỎ
        # 3. Còn lại -> GIỮ

        if is_collage:
            should_keep = False
            reason = f"Ảnh ghép (conf: {collage_conf:.2f})"
        elif self.require_person and not has_person:
            should_keep = False
            reason = "Không có người trong ảnh"
        elif has_person:
            reason = f"Có người (conf: {person_conf:.2f})"
        else:
            # Không require person, không phải collage -> giữ
            should_keep = True
            reason = "OK"

        return ImageFilterResult(
            path=str(path),
            has_person=has_person,
            is_collage=is_collage,
            should_keep=should_keep,
            reason=reason
        )

    def filter_folder(
        self,
        folder_path: str,
        output_folder: str = None,
        move_rejected: bool = False,
        on_progress: callable = None
    ) -> Tuple[List[ImageFilterResult], List[ImageFilterResult]]:
        """Lọc tất cả ảnh trong thư mục"""
        folder = Path(folder_path)
        if not folder.exists():
            return [], []

        # Tìm tất cả ảnh
        image_extensions = ['.jpg', '.jpeg', '.png', '.webp']
        images = []
        for ext in image_extensions:
            images.extend(folder.glob(f'*{ext}'))
            images.extend(folder.glob(f'*{ext.upper()}'))

        images = sorted(set(images))
        total = len(images)

        if total == 0:
            return [], []

        kept = []
        rejected = []

        for i, img_path in enumerate(images):
            if on_progress:
                on_progress(i + 1, total, img_path.name)

            result = self.filter_image(str(img_path))

            if result.should_keep:
                kept.append(result)
            else:
                rejected.append(result)

                if move_rejected:
                    rejected_folder = folder / "_rejected"
                    rejected_folder.mkdir(exist_ok=True)
                    try:
                        import shutil
                        shutil.move(str(img_path), str(rejected_folder / img_path.name))
                    except Exception as e:
                        console.print(f"[yellow]Không di chuyển được {img_path.name}: {e}[/]")

        # Copy ảnh tốt vào output folder nếu có
        if output_folder and kept:
            out = Path(output_folder)
            out.mkdir(parents=True, exist_ok=True)
            for i, result in enumerate(kept, 1):
                try:
                    import shutil
                    src = Path(result.path)
                    dst = out / f"{i:02d}{src.suffix}"
                    shutil.copy2(str(src), str(dst))
                except Exception as e:
                    console.print(f"[yellow]Không copy được {src.name}: {e}[/]")

        return kept, rejected

    def close(self):
        """Đóng resources"""
        if self._pose:
            self._pose.close()
            self._pose = None


def filter_product_images(
    folder_path: str,
    require_person: bool = True,
    reject_collage: bool = True,
    move_rejected: bool = True,
    on_log: callable = None
) -> Tuple[int, int]:
    """
    Utility function để lọc ảnh sản phẩm trong thư mục

    Args:
        folder_path: Thư mục chứa ảnh
        require_person: Yêu cầu có người
        reject_collage: Loại ảnh ghép
        move_rejected: Di chuyển ảnh bị loại vào _rejected
        on_log: Callback log

    Returns:
        Tuple (số_ảnh_giữ, số_ảnh_loại)
    """
    log = on_log or console.print

    filter_obj = ImageFilter(
        require_person=require_person,
        reject_collage=reject_collage
    )

    try:
        log(f"[cyan]🔍 Đang lọc ảnh trong {folder_path}...[/]")

        kept, rejected = filter_obj.filter_folder(
            folder_path,
            move_rejected=move_rejected,
            on_progress=lambda c, t, n: log(f"  [{c}/{t}] {n}")
        )

        log(f"[green]✓ Giữ {len(kept)} ảnh, loại {len(rejected)} ảnh[/]")

        for r in rejected:
            log(f"  [dim]❌ {Path(r.path).name}: {r.reason}[/]")

        return len(kept), len(rejected)

    finally:
        filter_obj.close()
