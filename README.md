# eye-of-sauron

Enables indoor testing with one swarm agent via overhead robot tracking and additional swarm member mocking over UDP.

## Setup
- Needs Python 3.8+. Install minimal deps:

```
python -m pip install opencv-python numpy
```

## Scripts
- `eye_of_sauron.py` — Live overhead robot tracker + UDP mock GPS
  - Run: `python eye_of_sauron.py`
  - Double-left-click in the window to spawn a simulated swarm member; double-click again near a member to remove it.
  - Broadcasts UDP to `255.255.255.255:5005` at 1 Hz.
  - Change camera, broadcast rate, or reference contour at the top of the file.
  - Default reference: `contour_refs/uuv_contour.png`.
  . Press `q` to quit.

- `test_find_robot.py` — Offline CV tester
    - Run: `python test_find_robot.py`
    - Iterates `test_imgs/`, displays detection results, and prints whether the robot was found.
    - Default reference: `contour_refs/uuv_contour.png`.
    - Press 'space' to advance to the next image, 'q' to quit.

- `sauronlib/find_robot.py` — CV help lib
  - Call `find_robot(frame, ref_image_path)` → returns `(contours, center)` or `(None, None)`.
  - Shows a `Reference Template` window when loading the contour.
  - Tweak `MAX_SCORE` and threshold values if detection is noisy.

## UDP Payloads
- UDP payloads printed by the app:
  - GPS: `GPS_<ts>_<x>_<y>`
  - Swarm: `SW_<ts>_<x>_<y>_0_0`

![sauron](https://www.pngkey.com/png/full/68-683125_eye-of-sauron-eye-of-sauron-symbol.png)

