<div align="center">

# ◈ NEXUS ULTRA

**مرکز فرماندهی سیستم**

<p>
  <img src="https://img.shields.io/badge/PLATFORM-WINDOWS-0078D6?style=for-the-badge&logo=windows&logoColor=white" alt="Windows">
  <img src="https://img.shields.io/badge/PYTHON-3.8%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/GUI-TKINTER-48D9FF?style=for-the-badge" alt="Tkinter">
  <img src="https://img.shields.io/badge/VOICE-FA%20%2F%20EN-37E6A5?style=for-the-badge" alt="Voice">
  <img src="https://img.shields.io/badge/LICENSE-MIT-green?style=for-the-badge" alt="License">
</p>

[اجرای سریع](#اجرای-سریع) · [دستورها](#دستورهای-صوتی--متنی) · [توصیه‌ها](#توصیهها-و-نکتهها) · [تلگرام](https://t.me/ArrowDeveloper) · [دونیت](https://donate.sudoshz.ir/u/spidey_team)

**🌐 [English](README.md) · فارسی**

**netMon · [NetMon Readme](INTEGRATION.md)**

*ساخته‌شده با ❤️ توسط **ArrowDeveloper***

</div>

---

<div dir="rtl">

## چی بهت می‌دم؟

NEXUS ULTRA یه داشبورد دسکتاپ مدرن با تم تیره برای ویندوزه که با پایتون و Tkinter ساخته شده. سیستم رو زنده مانیتور می‌کنه، وضعیت امنیت ویندوز رو چک می‌کنه و یه **دستیار صوتی/متنی فارسی و انگلیسی** داره برای ناوبری سریع و باز کردن منابع امنیت سایبری.

- 📊 **نمای کلی**: نمودار زنده CPU، رم، دیسک و شبکه همراه با ساعت و انیمیشن
- 🛡️ **مرکز امنیت**: وضعیت Windows Defender و فایروال و دکمه اسکن سریع (با تأیید قبلی)
- ▤ **پردازش‌های زنده**: لیست پردازش‌ها با PID، کاربر، مصرف CPU و حافظه
- ⌁ **مانیتور شبکه**: اتصالات فعال و پردازشی که پشت هر اتصاله
- 🎙️ **دستیار صوتی**: فرمان صوتی یا متنی به فارسی و انگلیسی، با پاسخ صوتی
- 📜 **گزارش رویدادها**: تایم‌لاین کارهای انجام‌شده (آخرین ۳۵۰ رویداد)

## پیش‌نیازها

| مورد | جزئیات |
|------|--------|
| سیستم‌عامل | ویندوز ۱۰ یا ۱۱ (بخش امنیت از PowerShell استفاده می‌کنه) |
| پایتون | نسخه ۳.۸ یا بالاتر، همراه با Tkinter (توی نصب‌کننده رسمی هست) |
| ضروری | `psutil` |
| اختیاری | `matplotlib` (نمودارها)، `pyttsx3` (پاسخ صوتی)، `SpeechRecognition` + `PyAudio` (میکروفون) |

> اگه پکیج‌های اختیاری نصب نباشن برنامه باز هم اجرا می‌شه، فقط اون قابلیت‌ها غیرفعال می‌مونن.

## اجرای سریع

</div>

```bash
# ۱. دریافت پروژه
git clone https://github.com/rv9cy/nexus-ultra.git
cd nexus-ultra

# ۲. نصب کتابخونه‌ها
pip install psutil matplotlib pyttsx3 SpeechRecognition PyAudio

# ۳. اجرا
python nexsus.py
```

<div dir="rtl">

اگه **uv** داری:

</div>

```bash
uv run --with psutil --with matplotlib --with pyttsx3 --with SpeechRecognition --with PyAudio nexsus.py
```

<div dir="rtl">

> 💡 اگه نصب `PyAudio` توی ویندوز خطا داد: `pip install pipwin && pipwin install pyaudio`

### انتخاب میکروفون

</div>

```powershell
$env:NEXUS_MICROPHONE_INDEX = "1"
python nexsus.py
```

<div dir="rtl">

## دستورهای صوتی / متنی

وارد بخش **Voice Assistant** شو و دکمه **START VOICE** رو بزن یا دستور رو تایپ کن.

| دستور | کاری که می‌کنه |
|-------|----------------|
| داشبورد / `dashboard` | باز شدن نمای کلی |
| مرکز امنیت / `security` | باز شدن مرکز امنیت |
| پردازش / `processes` | باز شدن پردازش‌های زنده |
| شبکه / `network` | باز شدن مانیتور شبکه |
| گزارش رویداد / `event logs` | باز شدن گزارش رویدادها |
| ساعت / تاریخ | گفتن ساعت یا تاریخ فعلی |
| گوگل / یوتیوب | باز کردن سایت |
| باگ بانتی / `bug bounty` | HackerOne، Bugcrowd، Intigriti، YesWeHack |
| آسیب‌پذیری / `cve` | CVE.org، NVD، CISA |
| `owasp` | سایت OWASP و Top Ten |
| اخبار امنیتی | The Hacker News، BleepingComputer، Dark Reading |
| تست نفوذ / `pentest` | ابزارهای Kali، Exploit-DB |
| رد تیم / بلو تیم | MITRE ATT&CK، CISA، Microsoft Security |
| فیشینگ | منابع CISA و MITRE |
| بدافزار | VirusTotal، Malware-Traffic-Analysis |
| خروج | بستن برنامه (با تأیید) |
| خاموش | خاموش کردن ویندوز بعد ۳۰ ثانیه (با تأیید) |

## توصیه‌ها و نکته‌ها

- ✅ برای دیدن همه جزئیات پردازش‌ها و شبکه، برنامه رو با **Administrator** اجرا کن.
- 🌐 تشخیص گفتار از سرویس آنلاین گوگل استفاده می‌کنه، پس برای میکروفون اینترنت لازمه.
- 🔒 اسکن سریع، خروج و خاموش کردن همیشه اول ازت تأیید می‌گیرن.
- 🧩 فقط ویندوز: روی لینوکس و مک رابط باز می‌شه ولی بخش‌های امنیتی پیام «Windows-only» می‌دن.

</div>

---

<div align="center">

## 💬 ارتباط و حمایت

[![Telegram](https://img.shields.io/badge/Telegram-@ArrowDeveloper-26A5E4?style=for-the-badge&logo=telegram&logoColor=white)](https://t.me/ArrowDeveloper)
[![Donate](https://img.shields.io/badge/Donate-Support%20Me-FF5E5B?style=for-the-badge)](https://donate.sudoshz.ir/u/spidey_team)

اگه پروژه به دردت خورد، یه ⭐ بده و عضو کانال تلگرام شو.

**Developed by ArrowDeveloper**

</div>
