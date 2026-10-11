# Lenovo Legion M600 Linux Control

Are you tired of booting into Windows or spinning up a virtual machine just because your Lenovo Legion M600 requires proprietary software that doesn't work on Linux? Worry no more! **Lenovo Legion M600 Linux Control** brings native hardware configuration directly to your Linux desktop, communicating with your mouse (`17ef:60e6`) over its 2.4GHz USB wireless dongle or USB cable.

This project was built **purely using AI**, combining a Python `hidapi` backend with a dark-mode PyQt5 interface packaged into a standalone Linux AppImage. **If you are experienced with coding and want to help clean up the codebase, optimize the app, or fix the remaining protocol bugs, please contact me!**

* **Idea & Protocol Inspiration:** [Keksuccino / Legion-M600-Manager-MacOS](https://github.com/Keksuccino/Legion-M600-Manager-MacOS/tree/main)

---

## Features

* **Live Dashboard & Persistent Battery Monitoring:** Checks whether the mouse is actively connected to the 2.4GHz receiver and displays the real-time battery percentage. When the mouse enters sleep mode, the app retains the last read battery percentage rather than resetting, updating automatically once the mouse wakes up, and includes a charging animation toggle for wired use.


* **DPI Stage Tuning:** Customize and switch between 4 onboard DPI stages (400 to 16,000 DPI) mapped to the mouse's internal sensor index table.


* **RGB Lighting Effects:** Configure dual-zone RGB lighting with **Static**, **Breathing**, **Rainbow**, or **Off** presets using a built-in color picker.


* **8-Button Remapping:** Rebind all 8 physical mouse buttons to standard mouse clicks, DPI switching, multimedia controls (Play/Pause, Volume Up, Volume Down, Mute), or disable specific buttons entirely, saving settings directly to the mouse's onboard memory.


* **Automatic Permission Setup:** Uses PolicyKit (`pkexec`) to prompt for your root password on first launch, automatically installing and reloading the required `udev` hardware rules so you never have to run the app as root.
* **Local Profile Persistence:** Saves your custom DPI values locally to `~/.m600_config.json` so your settings are remembered between reboots.

> **Where is the polling rate setting?**
> Software polling rate options have been intentionally removed. It is a wireless mouse after all—simply use the physical **HI / LO** switch on the underside of the mouse to toggle your polling rate!

---

## Dependencies

### Running the AppImage (`Legion-M600.AppImage`)

The AppImage bundles Python and its required libraries, relying only on basic host packages:

* **FUSE 3 (`fuse3` / `libfuse3`):** Required by the AppImage Type 2 runtime (FUSE 3.15.0 and `squashfuse` 0.5.2) along with `fusermount`, `/bin/mount`, and `/bin/umount` in your `$PATH` to mount the embedded squashfs image.


* **PolicyKit (`polkit`):** Required for `pkexec` to display the graphical password prompt when setting up `udev` rules.
* **Display Server & Graphics:** An active X11 or Wayland session (with `qt5-wayland` or XWayland) and standard OpenGL (`libgl`) libraries.

### Running from Source (`m600.py`)

If you prefer running the Python script directly, install the following packages via your package manager:

* **Arch Linux:** `sudo pacman -S python python-pyqt5 python-hidapi polkit`
* **Debian / Ubuntu:** `sudo apt install python3 python3-pyqt5 python3-hid policykit-1`
* **Fedora:** `sudo dnf install python3 python3-qt5 python3-hidapi polkit`

---

## Installation & Usage

1. Download `Legion-M600.AppImage` from the **Releases** page and make it executable:
```bash
chmod +x Legion-M600.AppImage

```


2. Launch the application as a normal user (do **not** use `sudo`):
```bash
./Legion-M600.AppImage

```


(If your system has FUSE issues, run `./Legion-M600.AppImage --appimage-extract-and-run` instead).


3. If prompted for hardware access on first launch, click **Yes**, enter your password, and unplug/re-plug your mouse dongle.

---

## Known Issues & Limitations

* **Forward Track & Back Track Commands Do Not Work:** Mapping buttons to **Multimedia: Next Track** (Forward Track) or **Multimedia: Previous Track** (Back Track) is currently non-functional.
* **Applying Settings During 2.4GHz Sleep Mode:** While the dashboard retains your last known battery level while the mouse is asleep, the hardware cannot receive new configuration payloads over the 2.4GHz wireless dongle until woken up. Move or click the mouse to wake it before applying new DPI, button, or lighting changes.


* **No Hardware Profile Readback:** Because the mouse firmware does not support reading current settings back to the host PC, the app tracks your saved DPI configuration locally via `~/.m600_config.json`.

---

## Contributing & Contact

Since this tool was built entirely with the help of AI, the code has plenty of room for improvement. **If you are better at coding and would like to help improve this project**—whether that's fixing the Next/Previous Track hex payloads, adding macro recording support, or refactoring the UI—please reach out to me directly, open an Issue, or submit a Pull Request on GitHub!
