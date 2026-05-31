# Bonkboard

Bonkboard is a lightweight, modern soundboard application designed for Linux. Built using Python, GTK4, and libadwaita, it provides a clean, responsive user interface that integrates beautifully with modern desktop environments.

By leveraging PulseAudio/PipeWire routing, Bonkboard dynamically configures dedicated virtual audio channels so you can stream your soundboard tracks directly into voice applications (such as Discord, Zoom, or OBS) while still monitoring them yourself. It also runs a background UDP socket server to listen for global, system-wide hotkeys.

---

## Features

* **Tabbed Sound Organization:** Group and categorize your audio files into custom tabs.
* **Seamless Drag & Drop:** Add sounds on the fly by dropping `.mp3`, `.wav`, `.ogg`, or `.m4a` files directly onto the window layout.
* **Automated Audio Routing:** Instantly creates a virtual sink and microphone clone upon launch—no manual virtual-cable or complicated configuration utilities required.
* **Network-Driven Global Hotkeys:** Control playback, trigger specific cards, or switch tabs via external custom system shortcuts.
* **Configurable Database Path:** Move and back up your sound library easily from the built-in settings menu.

---

## Prerequisites & Dependencies

To execute Bonkboard, you need Python 3 installed alongside the following system library dependencies and packages:

### Required System Packages

* **GTK4 & Libadwaita:** The native UI toolkit.
* **PyGObject (`gi`):** Python bindings for GTK/GObject.
* **PulseAudio / PipeWire (with Pulse emulation):** For routing command-line execution (`pactl` is strictly required).
* **mpv:** The backend command-line media player engine used for executing audio playbacks.

### Installation Commands

#### On Fedora

```
sudo dnf install python3-gobject gtk4 libadwaita mpv pulseaudio-utils

```

#### On Ubuntu / Debian / Linux Mint

```
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1 mpv pulseaudio-utils

```

#### On Arch Linux

```
sudo pacman -S python-gobject gtk4 libadwaita mpv libpulse

```

---

## How Audio Routing Works

When launched, Bonkboard invokes `pactl` to silently provision your virtual audio pipeline:

1. **`BonkboardSink`**: A virtual playback device where `mpv` pipes the audio track execution.
2. **`BonkboardMic`**: A remapped virtual recording source that mirrors/monitors whatever plays on `BonkboardSink`.

### Injecting Audio into Discord, OBS, or Voip Apps

1. Open your voice app settings (e.g., Discord **Settings** -> **Voice & Video**).
2. Change your **Input Device** (Microphone) to **`BonkboardVirtualMic`**.
3. **Important Note:** If you want people to hear *both* your physical microphone and your soundboard simultaneously, you must loop your physical mic into the soundboard's virtual pipeline. Run the following command in a terminal or add it to your startup script:

```
pactl load-module module-loopback source=YOUR_PHYSICAL_MIC_SOURCE_NAME sink=BonkboardSink

```

*(Replace `YOUR_PHYSICAL_MIC_SOURCE_NAME` with your actual hardware microphone source name found via `pactl list sources short`)*

---

## Understanding the Global Keybind System

Because standard desktop applications cannot capture keyboard events globally when minimized or unfocused, Bonkboard implements a local background UDP listener server bound to **`127.0.0.1:12345`**.

To control the application from anywhere in the OS, you simply send specific text payloads to this network port.

### Network API Command Strings

| Command | Description |
| --- | --- |
| `stop` | Immediately terminates all currently playing sounds and returns UI buttons to their normal state. |
| `tab:next` | Shifts the view screen to the next tab to the right. |
| `tab:prev` | Shifts the view screen to the previous tab to the left. |
| `tab:[index]` | Switches focus directly to a target tab matching a zero-based index number (e.g., `tab:0` = 1st tab, `tab:1` = 2nd tab). |
| `[index]` | Plays (or toggles stop) the specific sound card relative to its sequence placement on the **currently viewed tab** (e.g., sending `0` triggers the first track on the open tab, `1` triggers the second, etc.). |

---

## Setting Up Global System Hotkeys

To assign hardware key combinations to these actions, utilize your specific Desktop Environment's (GNOME, KDE, XFCE, i3/sway) native Custom Keyboard Shortcuts engine to fire shell utility network commands.

### Option A: Using native `/dev/udp` Bash scripting (Recommended)

Map a key sequence in your system settings to invoke a non-interactive bash call.

* **Kill All Sounds Shortcut** (e.g., bound to `Super + Escape`):

```
bash -c "echo 'stop' > /dev/udp/127.0.0.1/12345"

```

* **Play First Sound on Current Tab** (e.g., bound to `Ctrl + Numpad 1`):

```
bash -c "echo '0' > /dev/udp/127.0.0.1/12345"

```

* **Play Second Sound on Current Tab** (e.g., bound to `Ctrl + Numpad 2`):

```
bash -c "echo '1' > /dev/udp/127.0.0.1/12345"

```

* **Go to Next Tab Shortcut** (e.g., bound to `Ctrl + Page_Up`):

```
bash -c "echo 'tab:next' > /dev/udp/127.0.0.1/12345"

```

### Option B: Using `socat`

If your distribution or choice of execution shell doesn't natively map pseudo-device network routing, install `socat` via your package manager and configure your shortcuts like this:

```
echo "stop" | socat - UDP4:127.0.0.1:12345

```

---

## Installation & Launching

1. Save the source script as `bonkboard.py`.
2. Assign file permissions to mark it executable:

```
chmod +x bonkboard.py

```

3. Execute the script:

```
./bonkboard.py

```

### Storage and Configurations

All track names, file paths, and customized tabs layout records are stored within a structured JSON object.

By default, this is found at:
`~/.config/bonkboard/bonkboard_store.json`

If you want to move this database structure elsewhere (e.g., a shared cloud drive directory or a secondary storage folder), click the **Settings** gear icon inside the toolbar menu to dynamically choose a new target directory.
