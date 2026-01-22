# fix_arabic.py
import os
import sys

def fix_arabic_encoding():
    """إصلاح مشاكل الترميز العربية في ملف exe"""
    
    # التأكد من ترميز UTF-8 للنظام
    os.environ['PYTHONUTF8'] = '1'
    
    # إعداد ترميز المخرجات العربية
    if sys.platform == 'win32':
        import ctypes
        # تغيير صفحة الترميز في الكونسول
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)  # UTF-8
        ctypes.windll.kernel32.SetConsoleCP(65001)  # UTF-8
    
    # إعداد الترميز الافتراضي
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8