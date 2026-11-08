<div align="center">

# ◈ NEXUS ULTRA

**System Command Center**

<p>
  <img src="https://img.shields.io/badge/PLATFORM-WINDOWS-0078D6?style=for-the-badge&logo=windows&logoColor=white" alt="Windows">
  <img src="https://img.shields.io/badge/PYTHON-3.8%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/GUI-TKINTER-48D9FF?style=for-the-badge" alt="Tkinter">
  <img src="https://img.shields.io/badge/VOICE-FA%20%2F%20EN-37E6A5?style=for-the-badge" alt="Voice">
  <img src="https://img.shields.io/badge/LICENSE-MIT-green?style=for-the-badge" alt="License">
</p>

[Quick Start](#quick-start) · [Commands](#voice--text-commands) · [Tips](#tips--notes) · [Telegram](https://t.me/ArrowDeveloper) · [Donate](https://donate.sudoshz.ir/u/spidey_team)

**🌐 English · [فارسی](README.fa.md)**

*Made with ❤️ by **ArrowDeveloper***

</div>

---

## What You Get

NEXUS ULTRA is a modern dark-themed desktop dashboard for Windows, built with Python and Tkinter. It monitors your system in real time, checks Windows security status, and includes a **Persian + English voice/text assistant** for quick navigation and cybersecurity resources.

- 📊 **Overview**: live CPU, RAM, disk and network graphs with an animated orb and clock
- 🛡️ **Security Center**: Windows Defender and Firewall status, plus a Quick Scan button (asks for confirmation)
- ▤ **Live Processes**: running processes with PID, user, CPU and memory usage
- ⌁ **Network Monitor**: active connections and the process owning each one
- 🎙️ **Voice Assistant**: speak or type commands in Persian or English, with text-to-speech replies
- 📜 **Event Logs**: a timeline of everything NEXUS does (last 350 events)

## Requirements

| Item | Details |
|------|---------|
| OS | Windows 10 / 11 (security features use PowerShell) |
| Python | 3.8 or newer, with Tkinter (included in the standard installer) |
| Required | `psutil` |
| Optional | `matplotlib` (graphs), `pyttsx3` (voice replies), `SpeechRecognition` + `PyAudio` (microphone input) |

> The app still starts if optional packages are missing; those features are just disabled.

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/rv9cy/nexus-ultra.git
cd nexus-ultra

# 2. Install dependencies
pip install psutil matplotlib pyttsx3 SpeechRecognition PyAudio

# 3. Run
python nexsus.py
```

Using **uv**?

```bash
uv run --with psutil --with matplotlib --with pyttsx3 --with SpeechRecognition --with PyAudio nexsus.py
```

> 💡 If `PyAudio` fails to install on Windows: `pip install pipwin && pipwin install pyaudio`

### Choosing a microphone

```powershell
$env:NEXUS_MICROPHONE_INDEX = "1"
python nexsus.py
```

## Voice / Text Commands

Open **Voice Assistant**, then press **START VOICE** or type a command.

| Say (EN) | Say (FA) | Action |
|----------|----------|--------|
| `dashboard` / `overview` | داشبورد | Open Overview |
| `security` / `defender` | مرکز امنیت | Open Security Center |
| `processes` | پردازش | Open Live Processes |
| `network` | شبکه | Open Network Monitor |
| `event logs` | گزارش رویداد | Open Event Logs |
| `time` / `date` | ساعت / تاریخ | Speak the current time / date |
| `google` / `youtube` | گوگل / یوتیوب | Open the website |
| `bug bounty` | باگ بانتی | HackerOne, Bugcrowd, Intigriti, YesWeHack |
| `cve` | آسیب‌پذیری | CVE.org, NVD, CISA KEV |
| `owasp` | OWASP | OWASP and Top Ten |
| `security news` | اخبار امنیتی | The Hacker News, BleepingComputer, Dark Reading |
| `pentest` | تست نفوذ | Kali tools, Exploit-DB |
| `red team` / `blue team` | رد تیم / بلو تیم | MITRE ATT&CK, CISA, Microsoft Security |
| `phishing` | فیشینگ | CISA and MITRE T1566 |
| `malware` | بدافزار | VirusTotal, Malware-Traffic-Analysis |
| `exit nexus` | خروج | Close the app (confirmation) |
| `shutdown computer` | خاموش | Shut down Windows in 30 s (confirmation) |

## Tips & Notes

- ✅ Run as **Administrator** for full process and network details.
- 🌐 Speech recognition uses Google's online service, so the microphone needs an internet connection.
- 🔒 Quick Scan, Exit and Shutdown always ask for confirmation first.
- 🧩 Windows-only: on Linux/macOS the UI opens, but security features show "Windows-only feature."

---

<div align="center">

## 💬 Contact & Support

[![Telegram](https://img.shields.io/badge/Telegram-@ArrowDeveloper-26A5E4?style=for-the-badge&logo=telegram&logoColor=white)](https://t.me/ArrowDeveloper)
[![Donate](https://img.shields.io/badge/Donate-Support%20Me-FF5E5B?style=for-the-badge)](https://donate.sudoshz.ir/u/spidey_team)

If you like this project, drop a ⭐ and join the Telegram channel.

**Developed by ArrowDeveloper**

</div>
