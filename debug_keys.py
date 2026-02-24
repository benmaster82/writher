"""
Esegui questo script per vedere esattamente cosa riporta pynput
quando premi i tasti. Utile per diagnosticare AltGr su Windows.

  python debug_keys.py

Premi i tasti che vuoi testare, poi Esc per uscire.
"""
from pynput import keyboard
from pynput.keyboard import Key, KeyCode

print("=== Writher key debugger ===")
print(f"Key.alt_r  = {Key.alt_r!r}")
print(f"Key.ctrl_l = {Key.ctrl_l!r}")
print()
print("Premi i tasti (Esc per uscire)...")
print()


def on_press(key):
    info = f"PRESS   {key!r:<30} type={type(key).__name__}"
    if isinstance(key, KeyCode) and key.vk is not None:
        info += f"  vk={key.vk} (0x{key.vk:02X})"
    match = " <-- HOTKEY RILEVATO" if key == Key.alt_r else ""
    if isinstance(key, KeyCode) and key.vk == 165:
        match = " <-- HOTKEY RILEVATO (via vk)"
    print(info + match)


def on_release(key):
    info = f"RELEASE {key!r:<30} type={type(key).__name__}"
    if isinstance(key, KeyCode) and key.vk is not None:
        info += f"  vk={key.vk} (0x{key.vk:02X})"
    print(info)
    if key == Key.esc:
        return False


with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
    listener.join()
