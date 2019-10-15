# nvtk_mp4_to_gpx
Python script for extracting GPS data from dash cam video files (based on Novatek chipsets).

This script is based on original script file from Sergei at https://sergei.nz/extracting-gps-data-from-viofo-a119-and-other-novatek-powered-cameras/ with my modifications:
- parse many video files/directories at once and combine all GNSS data at one output .gpx file. You do not need use video/text editor software anymore.
- new parser algo "direct searching". Now you be able to extract gpx from MANY more dash cam files.
