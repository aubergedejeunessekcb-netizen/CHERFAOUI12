# build_exe.py
import sys
import os
from pathlib import Path
import PyInstaller.__main__
import shutil

# مسار الملف الرئيسي
main_script = 'main.py'
app_name = 'بيت_الشباب_كريم_جلول'

# إعدادات PyInstaller
args = [
    main_script,
    '--name=%s' % app_name,
    '--onefile',  # ملف تنفيذي واحد
    '--windowed',  # بدون نافذة كونسول
    '--icon=icons/app_icon.ico',  # أيقونة التطبيق
    '--add-data=data;data',  # إضافة مجلد البيانات
    '--add-data=icons;icons',  # إضافة مجلد الأيقونات
    '--hidden-import=customtkinter',
    '--hidden-import=PIL',
    '--hidden-import=arabic_reshaper',
    '--hidden-import=bidi',
    '--hidden-import=reportlab',
    '--hidden-import=matplotlib',
    '--hidden-import=matplotlib.backends.backend_agg',
    '--collect-all=customtkinter',
    '--collect-all=PIL',
    '--clean',  # تنظيف الملفات المؤقتة
]

# تشغيل PyInstaller
print("جاري بناء ملف exe...")
PyInstaller.__main__.run(args)

print(f"تم إنشاء ملف exe بنجاح في مجلد dist/{app_name}.exe")