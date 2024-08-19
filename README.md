# nvtk_mp4_to_gpx
Python script for extracting GPS data from dash cam video files.

This script is based on original script file from Sergei at https://sergei.nz/extracting-gps-data-from-viofo-a119-and-other-novatek-powered-cameras/ with my modifications:
- parse many video files/directories at once and combine all GNSS data at one output .gpx file. You do not need use video/text editor software anymore.
- new parser algo "direct searching". Now you be able to extract gpx from MANY more video files.

## Usage:
**In cmd line:**

```python nvtk_mp42gpx_EgorKin_mod.py -i input_video_file.mp4 -o outputGPSinfo.gpx```

**To extract GPS info from all video files in current directory:**

```python nvtk_mp42gpx_EgorKin_mod.py -i * -o outputGPSinfo.gpx```
