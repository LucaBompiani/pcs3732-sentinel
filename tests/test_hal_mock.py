from src.sentinel.config import load_config
from src.sentinel.hal.mock import (
    camera,
    display,
    enroll_button,
    indicators,
    keypad,
    lock,
    presence,
    rfid,
)

CFG = load_config()


def test_lock_starts_locked_and_relocks():
    lk = lock.make(CFG)
    assert lk.is_locked() is True  # RNF03 fail-secure
    lk.unlock(5.0)
    assert lk.unlocks == [5.0]
    assert lk.is_locked() is True  # retorna ao estado seguro


def test_indicators_record_events():
    ind = indicators.make(CFG)
    ind.signal_granted()
    ind.signal_denied()
    assert "granted" in ind.events
    assert "denied" in ind.events


def test_display_buffers_messages():
    disp = display.make(CFG)
    disp.show("linha1", "linha2")
    disp.clear()
    assert disp.buffer[0] == ("linha1", "linha2")
    assert disp.buffer[-1] == ("", "")


def test_keypad_and_rfid_return_none_on_timeout():
    kp = keypad.make(CFG)
    rd = rfid.make(CFG)
    assert kp.read_pin(0) is None
    assert rd.read_uid(0) is None


def test_keypad_and_rfid_return_fed_values():
    kp = keypad.make(CFG)
    rd = rfid.make(CFG)
    kp.feed("1234")
    rd.feed("AABBCC")
    assert kp.read_pin(0) == "1234"
    assert rd.read_uid(0) == "AABBCC"


def test_presence_default_and_fed():
    pr = presence.make(CFG)
    assert pr.wait_for_presence(0) is True
    pr.feed(False, True)
    assert pr.wait_for_presence(0) is False
    assert pr.wait_for_presence(0) is True


def test_camera_capture_carries_label():
    cam = camera.make(CFG)
    cam.see("joao")
    frame = cam.capture()
    assert frame.label == "joao"


def test_enroll_button_default_press():
    btn = enroll_button.make(CFG)
    assert btn.wait_for_press(0) is True
