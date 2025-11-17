import os
import shutil
import subprocess
from celery import shared_task
from django.conf import settings
from .models import MovieFile, Reel, CourseVideo

from redis import Redis

# Redis ulanish
redis_client = Redis(host="localhost", port=6379, db=0)


@shared_task(bind=True)
def process_video_task(self, movie_file_id, input_path):

    try:
        movie_file = MovieFile.objects.get(id=movie_file_id)

        # Chiqish papkasi (oldisini tozalaymiz)
        output_dir = os.path.join(settings.MEDIA_ROOT, "hls", str(movie_file_id))
        if os.path.exists(output_dir):
            try:
                shutil.rmtree(output_dir)
            except Exception:
                pass
        os.makedirs(output_dir, exist_ok=True)

        output_m3u8 = os.path.join(output_dir, "playlist.m3u8")
        segment_pattern = os.path.join(output_dir, "segment_%05d.ts")

        # =============================================================
        # Windows uchun
        #  
        # ffmpeg_path = os.path.join(
        #     settings.BASE_DIR, "ffmpeg", "ffmpeg-8.0-essentials_build", "bin", "ffmpeg.exe"
        # )
        # =============================================================

        # Linux uchun
        ffmpeg_path = "ffmpeg"

        # ffmpeg komandasi
        command = [
            ffmpeg_path,
            "-i", input_path,
            # Transcode to H.264/AAC for better HLS/device compatibility
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-profile:v", "main",
            "-level", "4.0",
            "-c:a", "aac",
            "-b:a", "128k",
            # HLS settings
            "-start_number", "0",
            "-hls_time", "6",
            "-hls_list_size", "0",
            "-hls_segment_filename", segment_pattern,
            "-hls_flags", "independent_segments",
            "-f", "hls",
            output_m3u8,
        ]

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1,
        )

        # ffmpeg stderr oqimidan progressni olish
        for line in process.stderr:
            if "frame=" in line:
                redis_client.set(f"progress:{movie_file_id}", line.strip())

        log_path = os.path.join(settings.BASE_DIR, "ffmpeg.log")
        with open(log_path, "w") as f:
            for line in process.stdout:
                f.write(line)
            for line in process.stderr:
                f.write(line)
            
        process.wait()


        if process.returncode != 0:
            print(f"⚠️ FFmpeg xato bilan tugadi: {process.returncode}")
            redis_client.set(f"progress:{movie_file_id}", "error")
            return

        # Tugadi
        redis_client.set(f"progress:{movie_file_id}", "finished")

        # Modelga yozamiz
        movie_file.hls_playlist_url = f"/media/hls/{movie_file_id}/playlist.m3u8"
        movie_file.save()

        # Temp faylni o‘chiramiz
        if os.path.exists(input_path):
            try:
                os.remove(input_path)
            except PermissionError:
                print(f"⚠️ Faylni o‘chirishda muammo: {input_path}")

    except Exception as e:
        redis_client.set(f"progress:{movie_file_id}", f"error: {str(e)}")


@shared_task(bind=True)
def process_reel_task(self, reel_id, input_path):

    try:
        print(f"🎬 Reel task boshlandi: {reel_id}")
        reel = Reel.objects.get(id=reel_id)

        # chiqish papkasi (oldisini tozalaymiz)
        output_dir = os.path.join(settings.MEDIA_ROOT, "hls_reels", str(reel_id))
        if os.path.exists(output_dir):
            try:
                shutil.rmtree(output_dir)
            except Exception:
                pass
        os.makedirs(output_dir, exist_ok=True)

        output_m3u8 = os.path.join(output_dir, "playlist.m3u8")

        # ffmpeg manzili
        ffmpeg_path = os.path.join(
            settings.BASE_DIR, "ffmpeg", "ffmpeg-8.0-essentials_build", "bin", "ffmpeg.exe"
        )

        # segment nomi
        segment_pattern = os.path.join(output_dir, "segment_%05d.ts")

        # ffmpeg komandasi (transcode, moslik uchun)
        command = [
            ffmpeg_path,
            "-i", input_path,
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-profile:v", "main",
            "-level", "4.0",
            "-c:a", "aac",
            "-b:a", "128k",
            "-start_number", "0",
            "-hls_time", "5",
            "-hls_list_size", "0",
            "-hls_segment_filename", segment_pattern,
            "-hls_flags", "independent_segments",
            "-f", "hls",
            output_m3u8,
        ]

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,                 # universal_newlines=True o‘rnida
            encoding="utf-8",          # majburiy UTF-8
            errors="replace",          # agar belgini o‘qiy olmasa "?" qilib qo‘yadi
            bufsize=1,
        )

        for line in process.stderr:
            line = line.strip()
            if "frame=" in line:
                redis_client.set(f"progress:reel:{reel_id}", line)

        process.wait()

        if process.returncode != 0:
            print(f"⚠️ FFmpeg xato bilan tugadi: {process.returncode}")
            stderr_output = process.stderr.read()
            print(f"❌ FFmpeg error (reel_id={reel_id}):", stderr_output)
            redis_client.set(f"progress:reel:{reel_id}", "error")
            return

        # tugallandi
        redis_client.set(f"progress:reel:{reel_id}", "finished")

        # modelga yozamiz (relativ URL bo‘lishi kerak)
        reel.hls_playlist_url = f"/media/hls_reels/{reel_id}/playlist.m3u8"
        reel.save()

        # vaqtinchalik faylni o‘chiramiz
        if os.path.exists(input_path):
            try:
                os.remove(input_path)
            except PermissionError:
                print(f"⚠️ Faylni o‘chirishda muammo: {input_path}")

    except Exception as e:
        print(f"❌ Task error (reel_id={reel_id}): {e}")
        redis_client.set(f"progress:reel:{reel_id}", f"error: {str(e)}")

@shared_task(bind=True)
def process_course_video_task(self, course_video_id, input_path):
    try:
        cv = CourseVideo.objects.get(id=course_video_id)

        output_dir = os.path.join(settings.MEDIA_ROOT, "hls_courses", str(course_video_id))
        os.makedirs(output_dir, exist_ok=True)

        output_m3u8 = os.path.join(output_dir, "playlist.m3u8")
        segment_pattern = os.path.join(output_dir, "segment_%05d.ts")

        ffmpeg_path = os.path.join(
            settings.BASE_DIR, "ffmpeg", "ffmpeg-8.0-essentials_build", "bin", "ffmpeg.exe"
        )

        command = [
            ffmpeg_path,
            "-i", input_path,
            "-codec:v", "libx264",      # agar copy bilan muammo bo'lsa → re-encode tavsiya etiladi
            "-preset", "veryfast",
            "-crf", "23",
            "-codec:a", "aac",
            "-ac", "2",
            "-b:a", "128k",
            "-start_number", "0",
            "-hls_time", "10",
            "-hls_list_size", "0",
            "-hls_segment_filename", segment_pattern,
            "-hls_segment_type", "mpegts",
            "-f", "hls",
            output_m3u8,
        ]

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1,
        )

        for line in process.stderr:
            if "frame=" in line:
                redis_client.set(f"progress:course_video:{course_video_id}", line.strip())

        process.wait()

        if process.returncode != 0:
            redis_client.set(f"progress:course_video:{course_video_id}", "error")
            return

        # Save HLS URLs atomically to avoid any stale instance issues
        hls_url = f"{settings.MEDIA_URL}hls_courses/{course_video_id}/playlist.m3u8"
        hls_seg = f"{settings.MEDIA_URL}hls_courses/{course_video_id}/segment_%05d.ts"

        print(hls_url, "hls url")
        print(hls_seg)
        updated = CourseVideo.objects.filter(id=course_video_id).update(
            hls_playlist_url=hls_url,
            hls_segment_path=hls_seg,
        )
        if updated:
            redis_client.set(f"progress:course_video:{course_video_id}", "saved")

        redis_client.set(f"progress:course_video:{course_video_id}", "finished")

        # input_path ni o'chirish (task tugagach)
        if os.path.exists(input_path):
            try:
                os.remove(input_path)
            except PermissionError:
                pass
    except Exception as e:
        redis_client.set(f"progress:course_video:{course_video_id}", f"error: {str(e)}")
