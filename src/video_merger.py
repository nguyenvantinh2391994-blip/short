"""
Video Merger - Ghép video + nhạc + voice + chuyển cảnh
"""

import os
from pathlib import Path
from typing import List, Optional, Callable
from moviepy.editor import (
    VideoFileClip, AudioFileClip, CompositeAudioClip,
    concatenate_videoclips, vfx
)


class VideoMerger:
    """Ghép nhiều video thành 1, thêm nhạc nền và voice"""

    # Loại chuyển cảnh
    TRANSITION_FADE_BLACK = "fade_black"  # Mờ đen
    TRANSITION_CROSSFADE = "crossfade"    # Mix/hòa trộn

    def __init__(
        self,
        transition_type: str = TRANSITION_FADE_BLACK,
        transition_duration: float = 0.5,
        on_log: Optional[Callable[[str], None]] = None
    ):
        self.transition_type = transition_type
        self.transition_duration = transition_duration
        self.on_log = on_log or print

    def log(self, msg: str):
        """Log message"""
        self.on_log(msg)

    def merge_videos(
        self,
        video_paths: List[str],
        output_path: str,
        music_path: Optional[str] = None,
        voice_path: Optional[str] = None,
        music_volume: float = 0.3,
        voice_volume: float = 1.0,
        mute_original: bool = True
    ) -> bool:
        """
        Ghép nhiều video thành 1

        Args:
            video_paths: Danh sách đường dẫn video
            output_path: Đường dẫn output
            music_path: Đường dẫn file nhạc nền (optional)
            voice_path: Đường dẫn file voice (optional)
            music_volume: Âm lượng nhạc (0-1)
            voice_volume: Âm lượng voice (0-1)
            mute_original: Tắt âm thanh gốc của video (default: True)

        Returns:
            True nếu thành công
        """
        if not video_paths:
            self.log("Không có video để ghép")
            return False

        clips = []

        try:
            self.log(f"Đang load {len(video_paths)} video...")

            # Load tất cả video
            for i, path in enumerate(video_paths):
                if not os.path.exists(path):
                    self.log(f"  Không tìm thấy: {path}")
                    continue

                self.log(f"  [{i+1}/{len(video_paths)}] {Path(path).name}")
                clip = VideoFileClip(path)
                # Tắt âm thanh gốc nếu mute_original=True
                if mute_original:
                    clip = clip.without_audio()
                clips.append(clip)

            if not clips:
                self.log("Không có video hợp lệ")
                return False

            # Áp dụng chuyển cảnh
            self.log(f"Áp dụng chuyển cảnh: {self.transition_type}")

            if len(clips) > 1:
                if self.transition_type == self.TRANSITION_FADE_BLACK:
                    # Fade to black giữa các video
                    processed_clips = []
                    for i, clip in enumerate(clips):
                        # Fade out cuối mỗi clip (trừ clip cuối)
                        if i < len(clips) - 1:
                            clip = clip.fx(vfx.fadeout, self.transition_duration)
                        # Fade in đầu mỗi clip (trừ clip đầu)
                        if i > 0:
                            clip = clip.fx(vfx.fadein, self.transition_duration)
                        processed_clips.append(clip)
                    clips = processed_clips

                elif self.transition_type == self.TRANSITION_CROSSFADE:
                    # Crossfade - ghép với overlap
                    processed_clips = []
                    for i, clip in enumerate(clips):
                        if i > 0:
                            clip = clip.fx(vfx.fadein, self.transition_duration)
                        if i < len(clips) - 1:
                            clip = clip.fx(vfx.fadeout, self.transition_duration)
                        processed_clips.append(clip)
                    clips = processed_clips

            # Ghép video
            self.log("Đang ghép video...")
            if self.transition_type == self.TRANSITION_CROSSFADE and len(clips) > 1:
                # Crossfade với overlap
                final_clip = concatenate_videoclips(
                    clips,
                    method="compose",
                    padding=-self.transition_duration
                )
            else:
                final_clip = concatenate_videoclips(clips, method="compose")

            # Xử lý audio
            audio_clips = []

            # Voice (nếu có) - không bắt buộc
            if voice_path and os.path.exists(voice_path):
                self.log(f"Thêm voice: {Path(voice_path).name}")
                voice_audio = AudioFileClip(voice_path)
                # Cắt voice nếu dài hơn video
                if voice_audio.duration > final_clip.duration:
                    voice_audio = voice_audio.subclip(0, final_clip.duration)
                voice_audio = voice_audio.volumex(voice_volume)
                audio_clips.append(voice_audio)
            else:
                self.log("Không có voice - tiếp tục xử lý...")

            # Nhạc nền (nếu có) - cắt theo thời lượng video
            if music_path and os.path.exists(music_path):
                self.log(f"Thêm nhạc: {Path(music_path).name}")
                music_audio = AudioFileClip(music_path)

                # Cắt nhạc theo đúng thời lượng video
                video_duration = final_clip.duration
                self.log(f"  Thời lượng video: {video_duration:.1f}s")
                self.log(f"  Thời lượng nhạc gốc: {music_audio.duration:.1f}s")

                # Loop nhạc nếu ngắn hơn video
                if music_audio.duration < video_duration:
                    loops_needed = int(video_duration / music_audio.duration) + 1
                    self.log(f"  Loop nhạc {loops_needed} lần")
                    from moviepy.editor import concatenate_audioclips
                    music_clips_list = [music_audio] * loops_needed
                    music_audio = concatenate_audioclips(music_clips_list)

                # Cắt nhạc bằng đúng thời lượng video
                music_audio = music_audio.subclip(0, video_duration)
                music_audio = music_audio.volumex(music_volume)
                # Fade out nhạc ở cuối (2s)
                music_audio = music_audio.fx(vfx.audio_fadeout, 2)
                audio_clips.append(music_audio)
                self.log(f"  ✓ Đã cắt nhạc = {video_duration:.1f}s")

            # Ghép audio
            if audio_clips:
                self.log("Ghép audio...")
                final_audio = CompositeAudioClip(audio_clips)
                final_clip = final_clip.set_audio(final_audio)

            # Export
            self.log(f"Xuất video: {output_path}")
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)

            final_clip.write_videofile(
                output_path,
                codec='libx264',
                audio_codec='aac',
                temp_audiofile='temp-audio.m4a',
                remove_temp=True,
                fps=30,
                preset='medium',
                threads=4,
                logger=None  # Tắt log của moviepy
            )

            self.log(f"✓ Hoàn thành: {output_path}")
            return True

        except Exception as e:
            self.log(f"Lỗi ghép video: {e}")
            return False

        finally:
            # Cleanup
            for clip in clips:
                try:
                    clip.close()
                except:
                    pass


def get_music_for_index(music_folder: str, index: int) -> Optional[str]:
    """Lấy file nhạc theo thứ tự (lặp lại nếu hết)"""
    if not music_folder or not os.path.exists(music_folder):
        return None

    music_files = sorted([
        f for f in os.listdir(music_folder)
        if f.lower().endswith(('.mp3', '.wav', '.m4a', '.aac'))
    ])

    if not music_files:
        return None

    # Lấy theo index, lặp lại nếu hết
    music_file = music_files[index % len(music_files)]
    return os.path.join(music_folder, music_file)


def get_voice_for_code(voice_folder: str, product_code: str) -> Optional[str]:
    """Lấy file voice theo mã sản phẩm"""
    if not voice_folder or not os.path.exists(voice_folder):
        return None

    # Tìm file có tên chứa mã sản phẩm
    for f in os.listdir(voice_folder):
        if f.lower().endswith(('.mp3', '.wav', '.m4a', '.aac')):
            name = Path(f).stem.upper()
            if product_code.upper() in name or name in product_code.upper():
                return os.path.join(voice_folder, f)

    # Hoặc tìm file có tên chính xác
    for ext in ['.mp3', '.wav', '.m4a', '.aac']:
        path = os.path.join(voice_folder, f"{product_code}{ext}")
        if os.path.exists(path):
            return path

    return None
