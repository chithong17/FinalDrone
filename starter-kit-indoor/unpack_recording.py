"""Build offline sample MP4 + telemetry from any recording folder.

Usage:
    python unpack_recording.py <recording_folder> [--output-dir <out_dir>] [--ffmpeg <ffmpeg_path>]
    
Examples:
    python unpack_recording.py recordings/261105-174737-dataset
    python unpack_recording.py path/to/recording --output-dir sample_data/
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path


def _round_field(value, places=1):
    if isinstance(value, (int, float)) and math.isfinite(value):
        return round(float(value), places)
    return value


def find_ffmpeg(custom_path: str | None = None) -> str | None:
    if custom_path and Path(custom_path).is_file():
        return str(Path(custom_path).resolve())
    which_ffmpeg = shutil.which("ffmpeg")
    if which_ffmpeg:
        return which_ffmpeg
    # Windows default winget locations fallback
    common_locations = [
        Path(r"C:\Users\khoand\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.2-full_build\bin\ffmpeg.exe"),
        Path(r"C:\ffmpeg\bin\ffmpeg.exe"),
        Path(r"C:\Program Files\ffmpeg\bin\ffmpeg.exe"),
    ]
    for p in common_locations:
        if p.is_file():
            return str(p)
    return None


def extract_telemetry(rec_dir: Path) -> list[dict]:
    manifest_path = rec_dir / "manifest.json"
    tel_path = rec_dir / "telemetry.jsonl"
    if not manifest_path.is_file() or not tel_path.is_file():
        raise FileNotFoundError(f"Missing manifest.json or telemetry.jsonl in {rec_dir}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    video_parts = manifest.get("video_parts") or []
    video_t0 = video_parts[0]["clock"]["t0"] if video_parts else 0.0
    ac_sn = manifest.get("aircraft_sn", "")
    payload_key = manifest.get("payload_index") or "88-0-0"
    topic = f"thing/product/{ac_sn}/osd" if ac_sn else None

    rows = []
    with tel_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if topic and rec.get("topic") != topic:
                continue
            time_offset_s = round(rec.get("t", 0.0) - video_t0, 3)
            if time_offset_s < 0:
                continue
            data = rec.get("msg", {}).get("data", {})
            pl = data.get(payload_key) or {}
            batt = (data.get("battery") or {}).get("capacity_percent")
            rows.append(
                {
                    "time_offset_s": time_offset_s,
                    "alt_rel": _round_field(data.get("elevation")),
                    "attitude_head": _round_field(data.get("attitude_head")),
                    "gimbal_pitch": _round_field(pl.get("gimbal_pitch")),
                    "gimbal_yaw": _round_field(pl.get("gimbal_yaw")),
                    "battery": int(batt) if isinstance(batt, (int, float)) else batt,
                }
            )
    return rows


def build_mp4(rec_dir: Path, out_mp4: Path, ffmpeg_bin: str) -> None:
    video_dir = rec_dir / "video" / "p1"
    if not video_dir.is_dir():
        # Fallback to search any .ts segments under video/
        video_dir = rec_dir / "video"
    segs = sorted(video_dir.rglob("seg_*.ts"))
    if not segs:
        # Check if already has an mp4 inside recording
        existing_mp4 = list(rec_dir.glob("*.mp4"))
        if existing_mp4:
            print(f"[*] Found existing MP4: {existing_mp4[0]}, copying to {out_mp4}...")
            shutil.copyfile(existing_mp4[0], out_mp4)
            return
        raise FileNotFoundError(f"No video segments (seg_*.ts) found in {video_dir}")

    print(f"[*] Found {len(segs)} video segments (.ts). Merging with FFmpeg...")
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    concat_txt = out_mp4.parent / f"_concat_{rec_dir.name}.txt"
    concat_txt.write_text(
        "".join(f"file '{f.resolve().as_posix()}'\n" for f in segs),
        encoding="utf-8",
    )
    cmd = [
        ffmpeg_bin,
        "-y",
        "-loglevel",
        "error",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_txt),
        "-c",
        "copy",
        str(out_mp4),
    ]
    subprocess.run(cmd, check=True)
    concat_txt.unlink(missing_ok=True)
    print(f"[+] Output MP4 successfully created: {out_mp4} ({out_mp4.stat().st_size // (1024*1024)} MB)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("recording_dir", type=Path, help="Path to DJI recording folder (containing manifest.json, telemetry.jsonl, video/)")
    parser.add_argument("--output-dir", type=Path, default=Path("sample_data"), help="Target directory for converted dataset (default: sample_data/)")
    parser.add_argument("--name", type=str, default=None, help="Base filename prefix for output (default: recording folder name)")
    parser.add_argument("--skip-video", action="store_true", help="Skip video stitching, only extract telemetry JSON")
    parser.add_argument("--ffmpeg", type=str, default=None, help="Custom path to ffmpeg executable")
    args = parser.parse_args()

    rec_dir = args.recording_dir.resolve()
    if not rec_dir.is_dir():
        print(f"[!] Error: Recording directory not found: {rec_dir}", file=sys.stderr)
        return 1

    out_dir = args.output_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = args.name or "flight"
    out_mp4 = out_dir / f"{prefix}.mp4"
    out_tel = out_dir / f"{prefix}_telemetry.json"

    print(f"=== KHOI TAO DU LIEU LUYEN TAP TU BAN GHI: {rec_dir.name} ===")
    
    # 1. Video stitching
    if not args.skip_video:
        ffmpeg_bin = find_ffmpeg(args.ffmpeg)
        if not ffmpeg_bin:
            print("[!] Canh bao: Khong tim thay 'ffmpeg' trong he thong (PATH).", file=sys.stderr)
            print("    Vui long cai dat ffmpeg hoac truyen duong dan qua --ffmpeg <path_to_ffmpeg.exe>", file=sys.stderr)
            print("    Tam thoi bo qua ghep video, chi xuat telemetry.", file=sys.stderr)
        else:
            try:
                build_mp4(rec_dir, out_mp4, ffmpeg_bin)
            except Exception as e:
                print(f"[!] Loi khi ghep video: {e}", file=sys.stderr)

    # 2. Telemetry extraction
    try:
        rows = extract_telemetry(rec_dir)
        out_tel.write_text(json.dumps(rows, indent=2), encoding="utf-8")
        print(f"[+] Output Telemetry: {out_tel} ({len(rows)} telemetry entries synchronized)")
    except Exception as e:
        print(f"[!] Loi khi trich xuat telemetry: {e}", file=sys.stderr)
        return 1

    print("\n[OK] Hoan tat! Doi thi co the dung bo du lieu nay de test voi baseline:")
    print(f"   python baseline.py --source {out_mp4} --telemetry {out_tel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
