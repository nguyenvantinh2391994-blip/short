"""
Image Filter - Lọc ảnh sản phẩm
- Chỉ giữ ảnh có người (thật)
- Loại bỏ ảnh ghép/collage
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
    """Bộ lọc ảnh sản phẩm"""

    def __init__(
        self,
        require_person: bool = True,
        reject_collage: bool = True,
        min_person_confidence: float = 0.5,
        collage_threshold: float = 0.3,
    ):
        """
        Args:
            require_person: Yêu cầu ảnh phải có người
            reject_collage: Loại bỏ ảnh ghép
            min_person_confidence: Độ tin cậy tối thiểu để nhận diện người
            collage_threshold: Ngưỡng để coi là ảnh ghép
        """
        self.require_person = require_person
        self.reject_collage = reject_collage
        self.min_person_confidence = min_person_confidence
        self.collage_threshold = collage_threshold

        # Khởi tạo mediapipe pose detector (nhận diện người)
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
        """
        Phát hiện người trong ảnh

        Returns:
            Tuple (có_người, độ_tin_cậy)
        """
        if image is None:
            return False, 0.0

        # Thử MediaPipe Pose trước (nhận diện toàn thân)
        if self._pose is not None:
            try:
                # Convert BGR to RGB
                rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                results = self._pose.process(rgb_image)

                if results.pose_landmarks:
                    # Có pose landmarks -> có người
                    # Tính confidence dựa trên visibility của các điểm
                    visibilities = [lm.visibility for lm in results.pose_landmarks.landmark]
                    avg_visibility = sum(visibilities) / len(visibilities)
                    return True, avg_visibility
            except Exception as e:
                console.print(f"[dim]MediaPipe error: {e}[/]")

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
                    # Có ít nhất 1 khuôn mặt
                    # Confidence dựa trên kích thước face so với ảnh
                    max_area = max(w * h for (x, y, w, h) in faces)
                    img_area = image.shape[0] * image.shape[1]
                    confidence = min(max_area / img_area * 10, 1.0)  # Scale up, max 1.0
                    return True, confidence
            except Exception as e:
                console.print(f"[dim]Face detection error: {e}[/]")

        return False, 0.0

    def detect_collage(self, image: np.ndarray) -> Tuple[bool, float]:
        """
        Phát hiện ảnh ghép/collage

        Ảnh ghép thường có:
        - Đường biên thẳng rõ ràng chia ảnh
        - Nhiều vùng có histogram khác nhau rõ rệt
        - Grid pattern (chia đều thành 2, 4, 6... phần)

        Returns:
            Tuple (là_ảnh_ghép, độ_tin_cậy)
        """
        if image is None:
            return False, 0.0

        try:
            h, w = image.shape[:2]

            # 1. Kiểm tra đường biên dọc (chia ảnh thành 2+ cột)
            vertical_score = self._detect_vertical_borders(image)

            # 2. Kiểm tra đường biên ngang (chia ảnh thành 2+ hàng)
            horizontal_score = self._detect_horizontal_borders(image)

            # 3. Kiểm tra aspect ratio kỳ lạ (quá rộng hoặc quá cao)
            aspect_ratio = w / h
            aspect_score = 0.0
            if aspect_ratio > 2.5 or aspect_ratio < 0.4:
                aspect_score = 0.5  # Ảnh quá dài/rộng thường là ghép

            # 4. Kiểm tra histogram từng vùng (ảnh ghép có histogram khác nhau)
            region_score = self._detect_region_differences(image)

            # Tổng hợp score
            total_score = max(vertical_score, horizontal_score) * 0.4 + aspect_score * 0.2 + region_score * 0.4

            is_collage = total_score >= self.collage_threshold

            return is_collage, total_score

        except Exception as e:
            console.print(f"[dim]Collage detection error: {e}[/]")
            return False, 0.0

    def _detect_vertical_borders(self, image: np.ndarray) -> float:
        """Phát hiện đường biên dọc chia ảnh"""
        h, w = image.shape[:2]
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Dùng edge detection
        edges = cv2.Canny(gray, 50, 150)

        # Kiểm tra các vị trí chia (1/2, 1/3, 2/3, 1/4, 3/4...)
        check_positions = [w // 2, w // 3, 2 * w // 3, w // 4, 3 * w // 4]

        max_score = 0.0
        for pos in check_positions:
            if pos <= 10 or pos >= w - 10:
                continue

            # Đếm số pixel edge trong cột này
            col_slice = edges[:, pos-2:pos+3]  # Lấy 5 pixel xung quanh
            edge_count = np.sum(col_slice > 0)
            edge_ratio = edge_count / (h * 5)

            # Nếu > 30% là edge -> có đường biên
            if edge_ratio > 0.3:
                max_score = max(max_score, edge_ratio)

        return min(max_score * 2, 1.0)  # Scale up

    def _detect_horizontal_borders(self, image: np.ndarray) -> float:
        """Phát hiện đường biên ngang chia ảnh"""
        h, w = image.shape[:2]
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        edges = cv2.Canny(gray, 50, 150)

        check_positions = [h // 2, h // 3, 2 * h // 3, h // 4, 3 * h // 4]

        max_score = 0.0
        for pos in check_positions:
            if pos <= 10 or pos >= h - 10:
                continue

            row_slice = edges[pos-2:pos+3, :]
            edge_count = np.sum(row_slice > 0)
            edge_ratio = edge_count / (w * 5)

            if edge_ratio > 0.3:
                max_score = max(max_score, edge_ratio)

        return min(max_score * 2, 1.0)

    def _detect_region_differences(self, image: np.ndarray) -> float:
        """Phát hiện sự khác biệt giữa các vùng trong ảnh"""
        h, w = image.shape[:2]

        # Chia ảnh thành 4 phần
        mid_h, mid_w = h // 2, w // 2
        regions = [
            image[0:mid_h, 0:mid_w],         # Top-left
            image[0:mid_h, mid_w:w],         # Top-right
            image[mid_h:h, 0:mid_w],         # Bottom-left
            image[mid_h:h, mid_w:w],         # Bottom-right
        ]

        # Tính histogram cho mỗi vùng
        histograms = []
        for region in regions:
            if region.size == 0:
                continue
            hist = cv2.calcHist([region], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
            hist = cv2.normalize(hist, hist).flatten()
            histograms.append(hist)

        if len(histograms) < 4:
            return 0.0

        # So sánh histogram giữa các vùng
        differences = []
        for i in range(len(histograms)):
            for j in range(i + 1, len(histograms)):
                diff = cv2.compareHist(histograms[i], histograms[j], cv2.HISTCMP_BHATTACHARYYA)
                differences.append(diff)

        # Nếu các vùng quá khác nhau -> có thể là collage
        avg_diff = sum(differences) / len(differences) if differences else 0

        # Bình thường ảnh có avg_diff < 0.3, collage thường > 0.5
        score = max(0, (avg_diff - 0.3) / 0.4)  # Map 0.3-0.7 to 0-1

        return min(score, 1.0)

    def filter_image(self, image_path: str) -> ImageFilterResult:
        """
        Lọc một ảnh

        Args:
            image_path: Đường dẫn ảnh

        Returns:
            ImageFilterResult
        """
        path = Path(image_path)

        if not path.exists():
            return ImageFilterResult(
                path=str(path),
                has_person=False,
                is_collage=False,
                should_keep=False,
                reason="File không tồn tại"
            )

        # Đọc ảnh
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

        # Detect collage
        is_collage, collage_conf = self.detect_collage(image)

        # Quyết định giữ hay bỏ
        should_keep = True
        reason = ""

        if self.require_person and not has_person:
            should_keep = False
            reason = "Không có người trong ảnh"
        elif self.reject_collage and is_collage:
            should_keep = False
            reason = f"Ảnh ghép (conf: {collage_conf:.2f})"
        elif has_person:
            reason = f"Có người (conf: {person_conf:.2f})"
        else:
            reason = "Không phát hiện đặc điểm đặc biệt"

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
        """
        Lọc tất cả ảnh trong thư mục

        Args:
            folder_path: Thư mục chứa ảnh
            output_folder: Thư mục output (nếu muốn copy ảnh tốt)
            move_rejected: Di chuyển ảnh bị loại vào thư mục _rejected
            on_progress: Callback (current, total, image_name)

        Returns:
            Tuple (ảnh_giữ, ảnh_loại)
        """
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

                # Di chuyển ảnh bị loại nếu cần
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

    filter = ImageFilter(
        require_person=require_person,
        reject_collage=reject_collage
    )

    try:
        log(f"[cyan]Đang lọc ảnh trong {folder_path}...[/]")

        kept, rejected = filter.filter_folder(
            folder_path,
            move_rejected=move_rejected,
            on_progress=lambda c, t, n: log(f"  [{c}/{t}] {n}")
        )

        log(f"[green]✓ Giữ {len(kept)} ảnh, loại {len(rejected)} ảnh[/]")

        for r in rejected:
            log(f"  [dim]❌ {Path(r.path).name}: {r.reason}[/]")

        return len(kept), len(rejected)

    finally:
        filter.close()
