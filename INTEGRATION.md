# افزودن Network Monitor به NEXUS ULTRA

## ۱) نصب
فایل `nexus_netmon.py` رو کنار `nexsus.py` بذار. وابستگی اضافه نداره (فقط کتابخانه‌ی استاندارد پایتون).

## ۲) باز کردن در پنجره‌ی جدا (ساده‌ترین روش)
بالای `nexsus.py`:
```python
from nexus_netmon import open_window
```
و یک دکمه یا آیتم منو که صدا بزنه (به‌جای `root` اسم پنجره‌ی اصلی خودت رو بذار):
```python
tk.Button(toolbar, text="Network Monitor",
          command=lambda: open_window(root, lang="fa")).pack()
```

## ۳) جاسازی داخل یک تب یا پنل
```python
from nexus_netmon import NetworkMonitorFrame
NetworkMonitorFrame(my_tab, lang="fa").pack(fill="both", expand=True)
```

## ۴) هماهنگ‌کردن رنگ‌ها با NEXUS
```python
open_window(root, lang="fa", theme={
    "bg": "#0b0d12", "panel": "#141821", "fg": "#e8ecf4",
    "muted": "#8a93a8", "accent": "#00d4ff",
    "ok": "#2ecc71", "bad": "#ff4d5e", "warn": "#f5a524", "grid": "#232938",
})
```

## ۵) هشدار قطعی
```python
open_window(root, on_alert=lambda kind, msg: print(kind, msg))   # kind: outage_start | outage_end
```

## ۶) داده‌ها
فایل `config.json` و دیتابیس در پوشه‌ی `netmon_data` کنار `nexus_netmon.py` ساخته می‌شن. با `data_dir="..."` می‌تونی مسیر رو عوض کنی.

## نکته
پنجره‌ی مانیتور موقع بسته‌شدن، پینگ‌ها رو خودش متوقف می‌کنه و روی بسته‌شدن NEXUS تأثیری نمی‌ذاره.

---

# English summary
Drop `nexus_netmon.py` next to `nexsus.py`, then `from nexus_netmon import open_window` and call
`open_window(root, lang="fa")` from a button. Use `NetworkMonitorFrame(parent)` to embed it in a tab.
Pass `theme={...}` to match NEXUS colors and `on_alert=callback` for outage notifications.
