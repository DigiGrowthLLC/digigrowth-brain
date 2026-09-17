import sys
import subprocess

BUBBLE_SIZE = 320
MARGIN = 40
# Extra rightward shift (px, in the scaled-to-320-tall frame) applied to the crop
# window's default centered x-offset. Positive = crop window moves right, which
# moves the subject's face LEFT in the bubble; negative = window moves left,
# face moves RIGHT (and crops out anything to the right, e.g. a mirror in the
# background). Re-tuned 2026-09-17 against the new headcam-master.mp4 (a wider
# 1920x1080 recording, differently framed than the old clip -60 was tuned
# against) — verified centered via a red guideline test at x=160 across a
# shift sweep. Re-tune again (grab a frame, render a few offset previews,
# pick) if a differently-framed headcam clip is ever swapped in.
CROP_X_SHIFT = 0


def main():
    if len(sys.argv) < 4:
        print("Usage: python compose_outreach_video.py <headcam.mp4> <site_scroll.mp4> <output.mp4>")
        sys.exit(1)

    headcam = sys.argv[1]
    site_scroll = sys.argv[2]
    output = sys.argv[3]

    r = BUBBLE_SIZE // 2
    filter_complex = (
        f"[1:v]scale={BUBBLE_SIZE}:{BUBBLE_SIZE}:force_original_aspect_ratio=increase,"
        f"crop={BUBBLE_SIZE}:{BUBBLE_SIZE}:(iw-{BUBBLE_SIZE})/2+{CROP_X_SHIFT}:(ih-{BUBBLE_SIZE})/2,"
        f"format=yuva420p,"
        f"geq=lum='p(X,Y)':a='if(gt(pow(X-{r},2)+pow(Y-{r},2),{r}*{r}),0,255)'[circle];"
        f"[0:v][circle]overlay={MARGIN}:H-h-{MARGIN}[outv]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", site_scroll,
        "-i", headcam,
        "-filter_complex", filter_complex,
        "-map", "[outv]", "-map", "1:a",
        "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
        "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
        "-c:a", "aac",
        "-shortest",
        "-movflags", "+faststart",
        output,
    ]
    subprocess.check_call(cmd)
    print(f"Saved outreach video: {output}")


if __name__ == "__main__":
    main()
