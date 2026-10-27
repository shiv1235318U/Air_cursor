import cv2
import mediapipe as mp
import pyautogui
import math
import time

# ==================================================
# AIR MOUSE 2.0 - DROIDCAM
# Relative movement + hold/drag + index scroll
# ==================================================

CAMERA_INDEX = 0
MIRROR_CAMERA = False

# Cursor settings
SCREEN_W, SCREEN_H = pyautogui.size()
SENSITIVITY = 1.5
SMOOTHING = 0.25
DEAD_ZONE = 0.0015

# Click and hold settings
TOUCH_START = 0.045
TOUCH_RELEASE = 0.065
HOLD_CONFIRM_TIME = 0.10

# Scroll settings
SCROLL_SENSITIVITY = 1000000
SCROLL_DEAD_ZONE = 0.004
SCROLL_SMOOTHING = 0.35

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0

# Open camera
camera = cv2.VideoCapture(CAMERA_INDEX)
camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)

if not camera.isOpened():
    print("ERROR: Cannot open DroidCam.")
    raise SystemExit

mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils

# Cursor movement state
previous_x = None
previous_y = None
smooth_dx = 0.0
smooth_dy = 0.0

# Scroll state
previous_scroll_y = None
smooth_scroll = 0.0
scroll_remainder = 0.0

# Hold state
touch_started_at = None
mouse_is_down = False
last_touch = False

previous_mode = None
running = True


def release_mouse():
    """Release the left mouse button safely."""
    global mouse_is_down

    if mouse_is_down:
        try:
            pyautogui.mouseUp(button="left")
        except Exception:
            pass
        mouse_is_down = False


def reset_motion():
    """Reset movement references when switching gestures."""
    global previous_x, previous_y
    global smooth_dx, smooth_dy
    global previous_scroll_y, smooth_scroll, scroll_remainder

    previous_x = None
    previous_y = None
    smooth_dx = 0.0
    smooth_dy = 0.0
    previous_scroll_y = None
    smooth_scroll = 0.0
    scroll_remainder = 0.0


print("=" * 48)
print("             AIR MOUSE 2.0")
print("=" * 48)
print("Index + middle apart : Move cursor")
print("Touch both fingertips: Hold / drag")
print("Index finger only    : Scroll")
print("Separate fingertips  : Release mouse")
print("Q                    : Exit")
print("=" * 48)

try:
    with mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=1,
        model_complexity=0,
        min_detection_confidence=0.65,
        min_tracking_confidence=0.70
    ) as hands:

        while running:
            success, frame = camera.read()

            if not success:
                print("Camera frame unavailable.")
                time.sleep(0.02)
                continue

            if MIRROR_CAMERA:
                frame = cv2.flip(frame, 1)

            height, width = frame.shape[:2]
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = hands.process(rgb)

            status = "Show your hand"
            mode = "none"

            if result.multi_hand_landmarks:
                hand = result.multi_hand_landmarks[0]
                lm = hand.landmark

                mp_draw.draw_landmarks(
                    frame, hand, mp_hands.HAND_CONNECTIONS
                )

                # Finger states
                index_up = lm[8].y < lm[6].y
                middle_up = lm[12].y < lm[10].y

                # Mode 1: Index finger only = scrolling
                if index_up and not middle_up:
                    mode = "scroll"
                    status = "SCROLL - move index finger"

                    release_mouse()
                    touch_started_at = None
                    last_touch = False

                    if previous_mode != mode:
                        reset_motion()

                    # Track index fingertip vertically
                    finger_y = lm[8].y

                    if previous_scroll_y is not None:
                        dy = previous_scroll_y - finger_y

                        if abs(dy) < SCROLL_DEAD_ZONE:
                            dy = 0.0

                        smooth_scroll += (
                            dy - smooth_scroll
                        ) * SCROLL_SMOOTHING

                        scroll_remainder += (
                            smooth_scroll * SCROLL_SENSITIVITY
                        )

                        # Send whole scroll steps only
                        steps = int(scroll_remainder / 120)

                        if steps != 0:
                            pyautogui.scroll(steps)
                            scroll_remainder -= steps * 120

                    previous_scroll_y = finger_y

                # Mode 2: Index + middle fingers = cursor / hold
                elif index_up and middle_up:
                    mode = "move"

                    if previous_mode != mode:
                        reset_motion()

                    # Midpoint of the two fingertips
                    hand_x = (lm[8].x + lm[12].x) / 2
                    hand_y = (lm[8].y + lm[12].y) / 2

                    # Relative movement reference
                    if previous_x is None:
                        previous_x = hand_x
                        previous_y = hand_y

                    dx = hand_x - previous_x
                    dy = hand_y - previous_y

                    previous_x = hand_x
                    previous_y = hand_y

                    if abs(dx) < DEAD_ZONE:
                        dx = 0.0
                    if abs(dy) < DEAD_ZONE:
                        dy = 0.0

                    smooth_dx += (
                        dx - smooth_dx
                    ) * SMOOTHING
                    smooth_dy += (
                        dy - smooth_dy
                    ) * SMOOTHING

                    # Apply relative movement
                    if dx != 0.0 or dy != 0.0:
                        current_x, current_y = pyautogui.position()

                        move_x = round(
                            current_x
                            + smooth_dx * SCREEN_W * SENSITIVITY
                        )
                        move_y = round(
                            current_y
                            + smooth_dy * SCREEN_H * SENSITIVITY
                        )

                        # Stay away from physical screen corners
                        move_x = max(2, min(SCREEN_W - 3, move_x))
                        move_y = max(2, min(SCREEN_H - 3, move_y))

                        pyautogui.moveTo(
                            move_x, move_y, _pause=False
                        )

                    # Distance between index and middle fingertips
                    distance = math.hypot(
                        lm[8].x - lm[12].x,
                        lm[8].y - lm[12].y
                    )

                    # Hysteresis prevents rapid gesture switching
                    if last_touch:
                        touching = distance < TOUCH_RELEASE
                    else:
                        touching = distance < TOUCH_START

                    now = time.monotonic()

                    if touching:
                        if touch_started_at is None:
                            touch_started_at = now

                        status = "HOLD / DRAG"

                        if (
                            not mouse_is_down
                            and now - touch_started_at
                            >= HOLD_CONFIRM_TIME
                        ):
                            pyautogui.mouseDown(button="left")
                            mouse_is_down = True

                    else:
                        touch_started_at = None
                        status = "MOVE CURSOR"
                        release_mouse()

                    last_touch = touching

                else:
                    mode = "idle"
                    status = "Raise index + middle fingers"

                    release_mouse()
                    touch_started_at = None
                    last_touch = False
                    reset_motion()

                # Highlight index and middle fingertips
                for tip in (8, 12):
                    px = int(lm[tip].x * width)
                    py = int(lm[tip].y * height)

                    cv2.circle(
                        frame, (px, py), 8,
                        (0, 255, 0), -1
                    )

            else:
                # If tracking is lost, release any held button
                status = "HAND NOT DETECTED"
                release_mouse()
                touch_started_at = None
                last_touch = False
                reset_motion()
                mode = "none"

            previous_mode = mode

            cv2.putText(
                frame, status, (10, 35),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65,
                (0, 255, 0), 2
            )

            cv2.putText(
                frame, "Q = EXIT", (10, 70),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                (255, 255, 255), 2
            )

            cv2.imshow("Air Mouse 2.0", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

except pyautogui.FailSafeException:
    print("\nEmergency stop triggered at screen corner.")

except KeyboardInterrupt:
    print("\nStopped by keyboard.")

finally:
    release_mouse()
    camera.release()
    cv2.destroyAllWindows()
    print("Air Mouse stopped.")