#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
برنامج إدارة بيت الشباب "كريم جلول قلعة الشيخ بوعمامة"
إصدار 1.0 - يدعم اللغة العربية بالكامل
"""

import sys
import os
from pathlib import Path
import customtkinter as ctk
from PIL import Image, ImageTk
import arabic_reshaper
from bidi.algorithm import get_display
import sqlite3
from datetime import datetime, date
import json
from typing import Dict, List, Optional, Tuple
import shutil

# إعداد المسارات
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
GUESTS_IMG_DIR = DATA_DIR / "guests"
EXPORTS_DIR = DATA_DIR / "exports"
BACKUP_DIR = DATA_DIR / "backup"

# إنشاء المجلدات المطلوبة
for directory in [DATA_DIR, GUESTS_IMG_DIR, EXPORTS_DIR, BACKUP_DIR]:
    directory.mkdir(exist_ok=True)

class ArabicText:
    """فئة لمعالجة النصوص العربية وعرضها بشكل صحيح"""
    
    @staticmethod
    def reshape(text: str) -> str:
        """إعادة تشكيل النص العربي للعرض الصحيح"""
        if not text or not any('\u0600' <= c <= '\u06FF' for c in text):
            return text
        reshaped = arabic_reshaper.reshape(text)
        return get_display(reshaped)
    
    @staticmethod
    def create_label(master, text: str, **kwargs):
        """إنشاء تسمية بالنص العربي المعدل"""
        return ctk.CTkLabel(master, text=ArabicText.reshape(text), **kwargs)

class DatabaseManager:
    """مدير قاعدة البيانات"""
    
    def __init__(self):
        self.db_path = DATA_DIR / "database.db"
        self.init_database()
    
    def init_database(self):
        """تهيئة قاعدة البيانات والجداول"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # جدول النزلاء
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS guests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                birth_date DATE NOT NULL,
                birth_place TEXT NOT NULL,
                national_id TEXT UNIQUE NOT NULL,
                father_name TEXT,
                mother_name TEXT,
                address TEXT,
                gender TEXT CHECK(gender IN ('ذكر', 'أنثى')),
                phone_numbers TEXT,  -- JSON list
                photo_path TEXT,
                registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                notes TEXT
            )
        ''')
        
        # جدول الحجوزات
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guest_id INTEGER,
                room_number TEXT,
                bed_number TEXT,
                check_in DATE NOT NULL,
                check_out DATE,
                price_per_person REAL NOT NULL,
                total_price REAL,
                status TEXT DEFAULT 'نشط',
                payment_method TEXT,
                notes TEXT,
                FOREIGN KEY (guest_id) REFERENCES guests (id)
            )
        ''')
        
        # جدول الإعدادات (الأسعار، الغرف، إلخ)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        
        # إعدادات افتراضية
        default_settings = [
            ('room_count', '10'),
            ('bed_count', '30'),
            ('default_price', '1500.00'),
            ('institution_name', 'بيت الشباب كريم جلول قلعة الشيخ بوعمامة'),
            ('address', 'قلعة الشيخ بوعمامة، ولاية البيض'),
            ('phone', '049-123456'),
            ('free_days', '0')
        ]
        
        cursor.executemany(
            'INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)',
            default_settings
        )
        
        conn.commit()
        conn.close()
    
    def add_guest(self, guest_data: Dict) -> int:
        """إضافة نزيل جديد"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # تحويل قائمة أرقام الهواتف إلى JSON
        if 'phone_numbers' in guest_data and isinstance(guest_data['phone_numbers'], list):
            guest_data['phone_numbers'] = json.dumps(guest_data['phone_numbers'])
        
        # إعداد بيانات النزيل
        columns = []
        values = []
        placeholders = []
        
        for key, value in guest_data.items():
            if value is not None:
                columns.append(key)
                values.append(value)
                placeholders.append('?')
        
        query = f'''
            INSERT INTO guests ({', '.join(columns)})
            VALUES ({', '.join(placeholders)})
        '''
        
        cursor.execute(query, values)
        guest_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return guest_id
    
    def search_guests(self, search_term: str, search_by: str = 'name') -> List[Dict]:
        """بحث عن النزلاء"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if search_by == 'national_id':
            cursor.execute(
                'SELECT * FROM guests WHERE national_id LIKE ?',
                (f'%{search_term}%',)
            )
        else:
            cursor.execute(
                '''SELECT * FROM guests 
                WHERE first_name LIKE ? OR last_name LIKE ? 
                OR father_name LIKE ? OR mother_name LIKE ?''',
                (f'%{search_term}%', f'%{search_term}%', 
                 f'%{search_term}%', f'%{search_term}%')
            )
        
        guests = [dict(row) for row in cursor.fetchall()]
        
        # تحويل JSON لأرقام الهواتف
        for guest in guests:
            if guest.get('phone_numbers'):
                guest['phone_numbers'] = json.loads(guest['phone_numbers'])
        
        conn.close()
        return guests
    
    def get_statistics(self) -> Dict:
        """الحصول على الإحصائيات"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        stats = {}
        
        # عدد النزلاء
        cursor.execute('SELECT COUNT(*) FROM guests')
        stats['total_guests'] = cursor.fetchone()[0]
        
        # عدد النزلاء حسب الجنس
        cursor.execute('SELECT gender, COUNT(*) FROM guests GROUP BY gender')
        stats['gender_distribution'] = dict(cursor.fetchall())
        
        # عدد الحجوزات النشطة
        cursor.execute("SELECT COUNT(*) FROM bookings WHERE status = 'نشط'")
        stats['active_bookings'] = cursor.fetchone()[0]
        
        # إيرادات اليوم
        today = date.today().isoformat()
        cursor.execute('''
            SELECT SUM(total_price) FROM bookings 
            WHERE DATE(check_in) = ? AND status = 'نشط'
        ''', (today,))
        stats['today_revenue'] = cursor.fetchone()[0] or 0
        
        # توزيع النزلاء حسب مكان الميلاد (أعلى 10)
        cursor.execute('''
            SELECT birth_place, COUNT(*) as count 
            FROM guests 
            GROUP BY birth_place 
            ORDER BY count DESC 
            LIMIT 10
        ''')
        stats['top_birth_places'] = dict(cursor.fetchall())
        
        conn.close()
        return stats

class GuestRegistrationFrame(ctk.CTkFrame):
    """إطار تسجيل النزلاء"""
    
    def __init__(self, master, db_manager):
        super().__init__(master)
        self.db_manager = db_manager
        self.current_photo_path = None
        self.phone_numbers = []
        
        self.setup_ui()
    
    def setup_ui(self):
        """إعداد واجهة تسجيل النزلاء"""
        # العنوان
        title = ArabicText.create_label(
            self, 
            "تسجيل نزيل جديد - بيت الشباب كريم جلول",
            font=("Arial", 20, "bold")
        )
        title.pack(pady=20)
        
        # إطار الحقول
        form_frame = ctk.CTkFrame(self)
        form_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        # إنشاء حقول الإدخال
        self.fields = {}
        field_definitions = [
            ("first_name", "الاسم", "text"),
            ("last_name", "اللقب", "text"),
            ("birth_date", "تاريخ الميلاد", "date"),
            ("birth_place", "مكان الميلاد", "text"),
            ("national_id", "رقم بطاقة التعريف الوطني", "text"),
            ("father_name", "اسم الأب", "text"),
            ("mother_name", "اسم الأم", "text"),
            ("address", "العنوان", "text"),
            ("gender", "الجنس", "combo", ["ذكر", "أنثى"])
        ]
        
        for i, field_def in enumerate(field_definitions):
            row = i // 2
            col = i % 2
            
            if field_def[2] == 'combo':
                self.create_combo_field(form_frame, field_def, row, col)
            elif field_def[2] == 'date':
                self.create_date_field(form_frame, field_def, row, col)
            else:
                self.create_text_field(form_frame, field_def, row, col)
        
        # إطار أرقام الهواتف
        phone_frame = ctk.CTkFrame(form_frame)
        phone_frame.grid(row=5, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
        
        ArabicText.create_label(phone_frame, "أرقام الهواتف:").pack(side="left", padx=5)
        
        self.phone_entry = ctk.CTkEntry(phone_frame, width=200)
        self.phone_entry.pack(side="left", padx=5)
        
        add_phone_btn = ctk.CTkButton(
            phone_frame, 
            text="إضافة رقم",
            command=self.add_phone_number,
            width=80
        )
        add_phone_btn.pack(side="left", padx=5)
        
        self.phone_listbox = ctk.CTkTextbox(phone_frame, height=60, width=300)
        self.phone_listbox.pack(side="left", padx=5, pady=5)
        
        # إطار رفع الصورة
        photo_frame = ctk.CTkFrame(form_frame)
        photo_frame.grid(row=6, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
        
        ArabicText.create_label(photo_frame, "صورة بطاقة التعريف:").pack(side="left", padx=5)
        
        upload_btn = ctk.CTkButton(
            photo_frame,
            text="اختر صورة",
            command=self.upload_photo
        )
        upload_btn.pack(side="left", padx=5)
        
        self.photo_label = ArabicText.create_label(photo_frame, "لم يتم اختيار صورة")
        self.photo_label.pack(side="left", padx=5)
        
        # زر الحفظ
        save_btn = ctk.CTkButton(
            form_frame,
            text="حفظ بيانات النزيل",
            command=self.save_guest,
            fg_color="green",
            hover_color="darkgreen",
            height=40,
            font=("Arial", 14, "bold")
        )
        save_btn.grid(row=7, column=0, columnspan=2, pady=20)
    
    def create_text_field(self, parent, field_def, row, col):
        """إنشاء حقل نصي"""
        field_name, label, field_type = field_def
        ArabicText.create_label(parent, label).grid(
            row=row*2, column=col, sticky="w", padx=5, pady=(10, 0)
        )
        
        entry = ctk.CTkEntry(parent, width=250)
        entry.grid(row=row*2+1, column=col, padx=5, pady=(0, 10), sticky="w")
        self.fields[field_name] = entry
    
    def create_combo_field(self, parent, field_def, row, col):
        """إنشاء حقل قائمة منسدلة"""
        field_name, label, _, options = field_def
        ArabicText.create_label(parent, label).grid(
            row=row*2, column=col, sticky="w", padx=5, pady=(10, 0)
        )
        
        combo = ctk.CTkComboBox(parent, values=options, width=250)
        combo.set(options[0])
        combo.grid(row=row*2+1, column=col, padx=5, pady=(0, 10), sticky="w")
        self.fields[field_name] = combo
    
    def create_date_field(self, parent, field_def, row, col):
        """إنشاء حقل تاريخ"""
        field_name, label, _ = field_def
        ArabicText.create_label(parent, label).grid(
            row=row*2, column=col, sticky="w", padx=5, pady=(10, 0)
        )
        
        # نستخدم حقل نصي مع تلميح بتنسيق التاريخ
        entry = ctk.CTkEntry(parent, width=250, placeholder_text="YYYY-MM-DD")
        entry.grid(row=row*2+1, column=col, padx=5, pady=(0, 10), sticky="w")
        self.fields[field_name] = entry
    
    def add_phone_number(self):
        """إضافة رقم هاتف إلى القائمة"""
        phone = self.phone_entry.get().strip()
        if phone and phone not in self.phone_numbers:
            self.phone_numbers.append(phone)
            self.phone_listbox.insert("end", f"{phone}\n")
            self.phone_entry.delete(0, "end")
    
    def upload_photo(self):
        """رفع صورة بطاقة التعريف"""
        from tkinter import filedialog
        file_path = filedialog.askopenfilename(
            title="اختر صورة بطاقة التعريف",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp")]
        )
        
        if file_path:
            self.current_photo_path = file_path
            filename = os.path.basename(file_path)
            self.photo_label.configure(text=ArabicText.reshape(f"تم اختيار: {filename}"))
    
    def save_guest(self):
        """حفظ بيانات النزيل"""
        try:
            # جمع البيانات من الحقول
            guest_data = {}
            
            for field_name, widget in self.fields.items():
                if isinstance(widget, ctk.CTkEntry):
                    guest_data[field_name] = widget.get().strip()
                elif isinstance(widget, ctk.CTkComboBox):
                    guest_data[field_name] = widget.get()
            
            # التحقق من الحقول المطلوبة
            required_fields = ['first_name', 'last_name', 'national_id']
            for field in required_fields:
                if not guest_data.get(field):
                    raise ValueError(f"حقل {field} مطلوب")
            
            # إضافة أرقام الهواتف
            guest_data['phone_numbers'] = self.phone_numbers
            
            # حفظ الصورة إذا كانت موجودة
            if self.current_photo_path:
                # نسخ الصورة إلى مجلد الصور
                ext = os.path.splitext(self.current_photo_path)[1]
                new_filename = f"{guest_data['national_id']}{ext}"
                dest_path = GUESTS_IMG_DIR / new_filename
                shutil.copy(self.current_photo_path, dest_path)
                guest_data['photo_path'] = str(dest_path)
            
            # إضافة النزيل إلى قاعدة البيانات
            guest_id = self.db_manager.add_guest(guest_data)
            
            # عرض رسالة نجاح
            message = f"تم تسجيل النزيل بنجاح! رقم التسجيل: {guest_id}"
            ctk.CTkMessagebox(
                title="نجاح",
                message=ArabicText.reshape(message),
                icon="check"
            )
            
            # مسح الحقول
            self.clear_fields()
            
        except Exception as e:
            ctk.CTkMessagebox(
                title="خطأ",
                message=ArabicText.reshape(f"حدث خطأ: {str(e)}"),
                icon="cancel"
            )
    
    def clear_fields(self):
        """مسح جميع الحقول"""
        for widget in self.fields.values():
            if isinstance(widget, ctk.CTkEntry):
                widget.delete(0, "end")
            elif isinstance(widget, ctk.CTkComboBox):
                widget.set(widget.cget("values")[0])
        
        self.phone_numbers.clear()
        self.phone_listbox.delete("1.0", "end")
        self.current_photo_path = None
        self.photo_label.configure(text=ArabicText.reshape("لم يتم اختيار صورة"))

class StatisticsFrame(ctk.CTkFrame):
    """إطار عرض الإحصائيات"""
    
    def __init__(self, master, db_manager):
        super().__init__(master)
        self.db_manager = db_manager
        
        self.setup_ui()
        self.refresh_statistics()
    
    def setup_ui(self):
        """إعداد واجهة الإحصائيات"""
        # العنوان
        title = ArabicText.create_label(
            self,
            "الإحصائيات والتقارير - بيت الشباب",
            font=("Arial", 20, "bold")
        )
        title.pack(pady=20)
        
        # إطار عرض الإحصائيات
        self.stats_frame = ctk.CTkFrame(self)
        self.stats_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        # أزرار التصدير
        export_frame = ctk.CTkFrame(self)
        export_frame.pack(fill="x", padx=20, pady=10)
        
        export_pdf_btn = ctk.CTkButton(
            export_frame,
            text="تصدير تقرير PDF",
            command=self.export_pdf,
            fg_color="#2d5b8a",
            width=150
        )
        export_pdf_btn.pack(side="left", padx=10)
        
        export_excel_btn = ctk.CTkButton(
            export_frame,
            text="تصدير إحصاءات Excel",
            command=self.export_excel,
            fg_color="#2d8a2d",
            width=150
        )
        export_excel_btn.pack(side="left", padx=10)
        
        refresh_btn = ctk.CTkButton(
            export_frame,
            text="تحديث الإحصائيات",
            command=self.refresh_statistics,
            width=150
        )
        refresh_btn.pack(side="left", padx=10)
        
        # زر النسخ الاحتياطي
        backup_btn = ctk.CTkButton(
            export_frame,
            text="إنشاء نسخة احتياطية",
            command=self.create_backup,
            fg_color="#8a2d2d",
            width=150
        )
        backup_btn.pack(side="left", padx=10)
    
    def refresh_statistics(self):
        """تحديث عرض الإحصائيات"""
        # مسح المحتوى القديم
        for widget in self.stats_frame.winfo_children():
            widget.destroy()
        
        # الحصول على الإحصائيات من قاعدة البيانات
        stats = self.db_manager.get_statistics()
        
        # عرض الإحصائيات
        stat_items = [
            ("إجمالي النزلاء", stats.get('total_guests', 0)),
            ("الحجوزات النشطة", stats.get('active_bookings', 0)),
            ("إيرادات اليوم", f"{stats.get('today_revenue', 0):,.2f} د.ج"),
            ("ذكور", stats.get('gender_distribution', {}).get('ذكر', 0)),
            ("إناث", stats.get('gender_distribution', {}).get('أنثى', 0))
        ]
        
        for i, (label, value) in enumerate(stat_items):
            stat_frame = ctk.CTkFrame(self.stats_frame, width=200, height=100)
            stat_frame.grid(row=i//3, column=i%3, padx=10, pady=10, sticky="nsew")
            
            # تسمية القيمة
            value_label = ctk.CTkLabel(
                stat_frame,
                text=str(value),
                font=("Arial", 28, "bold"),
                text_color="#2d5b8a"
            )
            value_label.pack(expand=True)
            
            # تسمية الوصف
            ArabicText.create_label(
                stat_frame,
                label,
                font=("Arial", 14)
            ).pack()
        
        # إعداد توزيع الأعمدة
        for i in range(3):
            self.stats_frame.columnconfigure(i, weight=1)
    
    def export_pdf(self):
        """تصدير تقرير PDF"""
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas
            from reportlab.lib.units import cm
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            
            # تسجيل خط عربي (يجب توفير ملف الخط)
            try:
                pdfmetrics.registerFont(TTFont('Arabic', 'arial.ttf'))
            except:
                pass
            
            # إنشاء ملف PDF
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            pdf_path = EXPORTS_DIR / f"تقرير_بيت_الشباب_{timestamp}.pdf"
            
            c = canvas.Canvas(str(pdf_path), pagesize=A4)
            width, height = A4
            
            # العنوان
            c.setFont("Helvetica-Bold", 16)
            c.drawString(2*cm, height-2*cm, "تقرير بيت الشباب كريم جلول")
            
            # التاريخ
            c.setFont("Helvetica", 10)
            c.drawString(width-6*cm, height-2*cm, 
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            
            # الحصول على الإحصائيات
            stats = self.db_manager.get_statistics()
            
            # كتابة الإحصائيات
            y_position = height - 4*cm
            c.setFont("Helvetica-Bold", 12)
            
            stat_lines = [
                f"إجمالي النزلاء: {stats.get('total_guests', 0)}",
                f"الحجوزات النشطة: {stats.get('active_bookings', 0)}",
                f"إيرادات اليوم: {stats.get('today_revenue', 0):,.2f} د.ج",
                f"عدد الذكور: {stats.get('gender_distribution', {}).get('ذكر', 0)}",
                f"عدد الإناث: {stats.get('gender_distribution', {}).get('أنثى', 0)}"
            ]
            
            for line in stat_lines:
                c.drawString(2*cm, y_position, line)
                y_position -= 0.7*cm
            
            c.save()
            
            ctk.CTkMessagebox(
                title="نجاح",
                message=ArabicText.reshape(f"تم تصدير PDF إلى: {pdf_path.name}"),
                icon="check"
            )
            
        except Exception as e:
            ctk.CTkMessagebox(
                title="خطأ",
                message=ArabicText.reshape(f"خطأ في تصدير PDF: {str(e)}"),
                icon="cancel"
            )
    
    def export_excel(self):
        """تصدير إحصاءات إلى Excel"""
        try:
            import pandas as pd
            
            # الحصول على الإحصائيات
            stats = self.db_manager.get_statistics()
            
            # إنشاء DataFrame
            data = {
                'المؤشر': [
                    'إجمالي النزلاء',
                    'الحجوزات النشطة', 
                    'إيرادات اليوم',
                    'عدد الذكور',
                    'عدد الإناث'
                ],
                'القيمة': [
                    stats.get('total_guests', 0),
                    stats.get('active_bookings', 0),
                    f"{stats.get('today_revenue', 0):,.2f} د.ج",
                    stats.get('gender_distribution', {}).get('ذكر', 0),
                    stats.get('gender_distribution', {}).get('أنثى', 0)
                ]
            }
            
            df = pd.DataFrame(data)
            
            # حفظ كملف Excel
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            excel_path = EXPORTS_DIR / f"إحصائيات_{timestamp}.xlsx"
            
            df.to_excel(excel_path, index=False)
            
            ctk.CTkMessagebox(
                title="نجاح",
                message=ArabicText.reshape(f"تم تصدير Excel إلى: {excel_path.name}"),
                icon="check"
            )
            
        except ImportError:
            ctk.CTkMessagebox(
                title="تحذير",
                message="مكتبة pandas غير مثبتة. قم بتثبيتها عبر: pip install pandas",
                icon="warning"
            )
        except Exception as e:
            ctk.CTkMessagebox(
                title="خطأ",
                message=ArabicText.reshape(f"خطأ في تصدير Excel: {str(e)}"),
                icon="cancel"
            )
    
    def create_backup(self):
        """إنشاء نسخة احتياطية"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = BACKUP_DIR / f"backup_{timestamp}.db"
            
            # نسخ قاعدة البيانات
            shutil.copy(self.db_manager.db_path, backup_file)
            
            ctk.CTkMessagebox(
                title="نجاح",
                message=ArabicText.reshape(f"تم إنشاء نسخة احتياطية: {backup_file.name}"),
                icon="check"
            )
            
        except Exception as e:
            ctk.CTkMessagebox(
                title="خطأ",
                message=ArabicText.reshape(f"خطأ في النسخ الاحتياطي: {str(e)}"),
                icon="cancel"
            )

class SearchFrame(ctk.CTkFrame):
    """إطار البحث عن النزلاء"""
    
    def __init__(self, master, db_manager):
        super().__init__(master)
        self.db_manager = db_manager
        
        self.setup_ui()
    
    def setup_ui(self):
        """إعداد واجهة البحث"""
        # العنوان
        title = ArabicText.create_label(
            self,
            "بحث وتعديل بيانات النزلاء",
            font=("Arial", 20, "bold")
        )
        title.pack(pady=20)
        
        # إطار البحث
        search_frame = ctk.CTkFrame(self)
        search_frame.pack(fill="x", padx=20, pady=10)
        
        ArabicText.create_label(search_frame, "كلمة البحث:").pack(side="left", padx=5)
        
        self.search_entry = ctk.CTkEntry(search_frame, width=300)
        self.search_entry.pack(side="left", padx=5)
        
        search_type_combo = ctk.CTkComboBox(
            search_frame,
            values=["الاسم", "رقم البطاقة"],
            width=120
        )
        search_type_combo.set("الاسم")
        search_type_combo.pack(side="left", padx=5)
        
        search_btn = ctk.CTkButton(
            search_frame,
            text="بحث",
            command=lambda: self.search_guests(
                self.search_entry.get(),
                search_type_combo.get()
            ),
            width=80
        )
        search_btn.pack(side="left", padx=5)
        
        # إطار نتائج البحث
        results_frame = ctk.CTkFrame(self)
        results_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        # شجرة لعرض النتائج
        self.tree_frame = ctk.CTkFrame(results_frame)
        self.tree_frame.pack(fill="both", expand=True)
        
        # إنشاء Treeview مع تمرير الأفقي
        from tkinter import ttk
        
        tree_scroll = ttk.Scrollbar(self.tree_frame)
        tree_scroll.pack(side="right", fill="y")
        
        self.tree = ttk.Treeview(
            self.tree_frame,
            yscrollcommand=tree_scroll.set,
            selectmode="browse",
            height=15
        )
        tree_scroll.config(command=self.tree.yview)
        
        # تعريف الأعمدة
        self.tree['columns'] = ('id', 'name', 'national_id', 'gender', 'birth_date', 'phone')
        
        # تنسيق الأعمدة
        self.tree.column("#0", width=0, stretch=False)
        self.tree.column("id", width=50, minwidth=50)
        self.tree.column("name", width=200, minwidth=150)
        self.tree.column("national_id", width=150, minwidth=120)
        self.tree.column("gender", width=80, minwidth=80)
        self.tree.column("birth_date", width=100, minwidth=100)
        self.tree.column("phone", width=150, minwidth=120)
        
        # عناوين الأعمدة
        self.tree.heading("id", text="ID")
        self.tree.heading("name", text="الاسم الكامل")
        self.tree.heading("national_id", text="رقم البطاقة")
        self.tree.heading("gender", text="الجنس")
        self.tree.heading("birth_date", text="تاريخ الميلاد")
        self.tree.heading("phone", text="الهاتف")
        
        self.tree.pack(fill="both", expand=True)
        
        # أزرار الإجراءات
        action_frame = ctk.CTkFrame(results_frame)
        action_frame.pack(fill="x", pady=10)
        
        edit_btn = ctk.CTkButton(
            action_frame,
            text="تعديل المحدد",
            command=self.edit_selected,
            fg_color="orange",
            width=120
        )
        edit_btn.pack(side="left", padx=5)
        
        delete_btn = ctk.CTkButton(
            action_frame,
            text="حذف المحدد",
            command=self.delete_selected,
            fg_color="red",
            width=120
        )
        delete_btn.pack(side="left", padx=5)
        
        view_btn = ctk.CTkButton(
            action_frame,
            text="عرض التفاصيل",
            command=self.view_details,
            width=120
        )
        view_btn.pack(side="left", padx=5)
        
        print_btn = ctk.CTkButton(
            action_frame,
            text="طباعة البطاقة",
            command=self.print_card,
            fg_color="#2d5b8a",
            width=120
        )
        print_btn.pack(side="left", padx=5)
    
    def search_guests(self, search_term, search_type):
        """بحث عن النزلاء"""
        # مسح النتائج السابقة
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        if not search_term:
            return
        
        # البحث في قاعدة البيانات
        search_by = 'national_id' if search_type == 'رقم البطاقة' else 'name'
        guests = self.db_manager.search_guests(search_term, search_by)
        
        # عرض النتائج
        for guest in guests:
            full_name = f"{guest.get('last_name', '')} {guest.get('first_name', '')}"
            phone_numbers = guest.get('phone_numbers', [])
            primary_phone = phone_numbers[0] if phone_numbers else ""
            
            self.tree.insert(
                "", "end",
                values=(
                    guest['id'],
                    full_name,
                    guest.get('national_id', ''),
                    guest.get('gender', ''),
                    guest.get('birth_date', ''),
                    primary_phone
                )
            )
    
    def edit_selected(self):
        """تعديل النزيل المحدد"""
        selection = self.tree.selection()
        if not selection:
            ctk.CTkMessagebox.show_warning("تحذير", "يرجى اختيار نزيل لتعديله")
            return
        
        item = self.tree.item(selection[0])
        guest_id = item['values'][0]
        
        # هنا يمكنك فتح نافذة تعديل
        # لأجل البساطة، سنعرض رسالة
        ctk.CTkMessagebox.show_info(
            "تعديل",
            f"فتح نافذة تعديل للنزيل رقم {guest_id}"
        )
    
    def delete_selected(self):
        """حذف النزيل المحدد"""
        selection = self.tree.selection()
        if not selection:
            ctk.CTkMessagebox.show_warning("تحذير", "يرجى اختيار نزيل لحذفه")
            return
        
        item = self.tree.item(selection[0])
        guest_id = item['values'][0]
        
        # تأكيد الحذف
        confirm = ctk.CTkMessagebox(
            title="تأكيد الحذف",
            message="هل أنت متأكد من حذف هذا النزيل؟",
            icon="warning",
            option_1="إلغاء",
            option_2="حذف"
        )
        
        if confirm.get() == "حذف":
            # حذف النزيل من قاعدة البيانات
            try:
                conn = sqlite3.connect(self.db_manager.db_path)
                cursor = conn.cursor()
                cursor.execute("DELETE FROM guests WHERE id = ?", (guest_id,))
                conn.commit()
                conn.close()
                
                # حذف من العرض
                self.tree.delete(selection[0])
                
                ctk.CTkMessagebox.show_info("نجاح", "تم حذف النزيل بنجاح")
                
            except Exception as e:
                ctk.CTkMessagebox.showerror("خطأ", f"حدث خطأ أثناء الحذف: {str(e)}")
    
    def view_details(self):
        """عرض تفاصيل النزيل المحدد"""
        selection = self.tree.selection()
        if not selection:
            ctk.CTkMessagebox.show_warning("تحذير", "يرجى اختيار نزيل لعرضه")
            return
        
        item = self.tree.item(selection[0])
        guest_id = item['values'][0]
        
        # الحصول على تفاصيل النزيل من قاعدة البيانات
        conn = sqlite3.connect(self.db_manager.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM guests WHERE id = ?", (guest_id,))
        guest = cursor.fetchone()
        conn.close()
        
        if guest:
            guest_dict = dict(guest)
            
            # إنشاء نافذة التفاصيل
            details_window = ctk.CTkToplevel(self)
            details_window.title("تفاصيل النزيل")
            details_window.geometry("600x500")
            
            # عرض التفاصيل
            details_text = f"""
            الاسم الكامل: {guest_dict.get('last_name', '')} {guest_dict.get('first_name', '')}
            
            رقم البطاقة: {guest_dict.get('national_id', '')}
            
            تاريخ الميلاد: {guest_dict.get('birth_date', '')}
            
            مكان الميلاد: {guest_dict.get('birth_place', '')}
            
            اسم الأب: {guest_dict.get('father_name', '')}
            
            اسم الأم: {guest_dict.get('mother_name', '')}
            
            العنوان: {guest_dict.get('address', '')}
            
            الجنس: {guest_dict.get('gender', '')}
            
            تاريخ التسجيل: {guest_dict.get('registration_date', '')}
            """
            
            text_widget = ctk.CTkTextbox(details_window, width=580, height=400)
            text_widget.pack(padx=10, pady=10)
            text_widget.insert("1.0", ArabicText.reshape(details_text))
            text_widget.configure(state="disabled")
    
    def print_card(self):
        """طباعة بطاقة النزيل"""
        selection = self.tree.selection()
        if not selection:
            ctk.CTkMessagebox.show_warning("تحذير", "يرجى اختيار نزيل لطباعة بطاقته")
            return
        
        ctk.CTkMessagebox.show_info(
            "طباعة",
            "جاري تحضير البطاقة للطباعة..."
        )

class SettingsFrame(ctk.CTkFrame):
    """إطار الإعدادات"""
    
    def __init__(self, master, db_manager):
        super().__init__(master)
        self.db_manager = db_manager
        
        self.setup_ui()
        self.load_settings()
    
    def setup_ui(self):
        """إعداد واجهة الإعدادات"""
        # العنوان
        title = ArabicText.create_label(
            self,
            "إعدادات بيت الشباب",
            font=("Arial", 20, "bold")
        )
        title.pack(pady=20)
        
        # إطار الإعدادات
        settings_frame = ctk.CTkFrame(self)
        settings_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        # إعدادات الأسعار والغرف
        price_room_frame = ctk.CTkFrame(settings_frame)
        price_room_frame.pack(fill="x", padx=10, pady=10)
        
        # عدد الغرف
        ArabicText.create_label(price_room_frame, "عدد الغرف:").grid(
            row=0, column=0, sticky="w", padx=5, pady=5
        )
        
        self.room_count = ctk.CTkEntry(price_room_frame, width=100)
        self.room_count.grid(row=0, column=1, padx=5, pady=5)
        
        # عدد الأسرة
        ArabicText.create_label(price_room_frame, "عدد الأسرة:").grid(
            row=1, column=0, sticky="w", padx=5, pady=5
        )
        
        self.bed_count = ctk.CTkEntry(price_room_frame, width=100)
        self.bed_count.grid(row=1, column=1, padx=5, pady=5)
        
        # السعر الافتراضي للفرد
        ArabicText.create_label(price_room_frame, "السعر للفرد (د.ج):").grid(
            row=2, column=0, sticky="w", padx=5, pady=5
        )
        
        self.default_price = ctk.CTkEntry(price_room_frame, width=100)
        self.default_price.grid(row=2, column=1, padx=5, pady=5)
        
        # أيام المجانية
        ArabicText.create_label(price_room_frame, "أيام المجانية:").grid(
            row=3, column=0, sticky="w", padx=5, pady=5
        )
        
        self.free_days = ctk.CTkEntry(price_room_frame, width=100)
        self.free_days.grid(row=3, column=1, padx=5, pady=5)
        
        # زر حفظ الإعدادات
        save_settings_btn = ctk.CTkButton(
            settings_frame,
            text="حفظ الإعدادات",
            command=self.save_settings,
            fg_color="green",
            width=150
        )
        save_settings_btn.pack(pady=20)
        
        # قسم إدارة النسخ الاحتياطي
        backup_frame = ctk.CTkFrame(settings_frame)
        backup_frame.pack(fill="x", padx=10, pady=20)
        
        ArabicText.create_label(
            backup_frame,
            "إدارة النسخ الاحتياطية",
            font=("Arial", 14, "bold")
        ).pack(pady=10)
        
        restore_btn = ctk.CTkButton(
            backup_frame,
            text="استعادة نسخة احتياطية",
            command=self.restore_backup,
            width=180
        )
        restore_btn.pack(pady=5)
        
        auto_backup_btn = ctk.CTkButton(
            backup_frame,
            text="تفعيل النسخ التلقائي",
            command=self.toggle_auto_backup,
            width=180
        )
        auto_backup_btn.pack(pady=5)
    
    def load_settings(self):
        """تحميل الإعدادات من قاعدة البيانات"""
        try:
            conn = sqlite3.connect(self.db_manager.db_path)
            cursor = conn.cursor()
            
            settings_keys = ['room_count', 'bed_count', 'default_price', 'free_days']
            for key in settings_keys:
                cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
                result = cursor.fetchone()
                if result:
                    value = result[0]
                    # تعيين القيمة في الحقل المناسب
                    if key == 'room_count':
                        self.room_count.delete(0, "end")
                        self.room_count.insert(0, value)
                    elif key == 'bed_count':
                        self.bed_count.delete(0, "end")
                        self.bed_count.insert(0, value)
                    elif key == 'default_price':
                        self.default_price.delete(0, "end")
                        self.default_price.insert(0, value)
                    elif key == 'free_days':
                        self.free_days.delete(0, "end")
                        self.free_days.insert(0, value)
            
            conn.close()
            
        except Exception as e:
            print(f"خطأ في تحميل الإعدادات: {e}")
    
    def save_settings(self):
        """حفظ الإعدادات"""
        try:
            conn = sqlite3.connect(self.db_manager.db_path)
            cursor = conn.cursor()
            
            settings = [
                ('room_count', self.room_count.get()),
                ('bed_count', self.bed_count.get()),
                ('default_price', self.default_price.get()),
                ('free_days', self.free_days.get())
            ]
            
            for key, value in settings:
                cursor.execute(
                    "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                    (key, value)
                )
            
            conn.commit()
            conn.close()
            
            ctk.CTkMessagebox.show_info("نجاح", "تم حفظ الإعدادات بنجاح")
            
        except Exception as e:
            ctk.CTkMessagebox.showerror("خطأ", f"حدث خطأ في حفظ الإعدادات: {str(e)}")
    
    def restore_backup(self):
        """استعادة نسخة احتياطية"""
        from tkinter import filedialog
        
        file_path = filedialog.askopenfilename(
            title="اختر ملف النسخة الاحتياطية",
            filetypes=[("Database files", "*.db"), ("All files", "*.*")]
        )
        
        if file_path:
            confirm = ctk.CTkMessagebox(
                title="تأكيد الاستعادة",
                message="هل أنت متأكد من استعادة هذه النسخة؟ سيتم استبدال جميع البيانات الحالية.",
                icon="warning",
                option_1="إلغاء",
                option_2="استعادة"
            )
            
            if confirm.get() == "استعادة":
                try:
                    # إغلاق اتصالات قاعدة البيانات أولاً
                    import shutil
                    shutil.copy(file_path, self.db_manager.db_path)
                    
                    ctk.CTkMessagebox.show_info(
                        "نجاح",
                        "تم استعادة النسخة الاحتياطية بنجاح. يرجى إعادة تشغيل البرنامج."
                    )
                    
                except Exception as e:
                    ctk.CTkMessagebox.showerror(
                        "خطأ",
                        f"حدث خطأ في الاستعادة: {str(e)}"
                    )
    
    def toggle_auto_backup(self):
        """تفعيل/تعطيل النسخ التلقائي"""
        # هنا يمكنك إضافة منطق النسخ التلقائي
        ctk.CTkMessagebox.show_info(
            "معلومة",
            "ميزة النسخ التلقائي تحت التطوير. قم يدوياً بالنسخ الاحتياطي بانتظام."
        )

class MainApplication(ctk.CTk):
    """التطبيق الرئيسي"""
    
    def __init__(self):
        super().__init__()
        
        # إعداد النافذة الرئيسية
        self.title("بيت الشباب كريم جلول قلعة الشيخ بوعمامة")
        self.geometry("1200x700")
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")
        
        # تهيئة مدير قاعدة البيانات
        self.db_manager = DatabaseManager()
        
        # إعداد الواجهة
        self.setup_ui()
    
    def setup_ui(self):
        """إعداد واجهة التطبيق"""
        # شريط العنوان
        title_frame = ctk.CTkFrame(self, height=80)
        title_frame.pack(fill="x", padx=10, pady=5)
        
        title_label = ArabicText.create_label(
            title_frame,
            "🏠 بيت الشباب كريم جلول - قلعة الشيخ بوعمامة",
            font=("Arial", 24, "bold"),
            text_color="#2d5b8a"
        )
        title_label.pack(pady=20)
        
        ArabicText.create_label(
            title_frame,
            "نظام إدارة النزلاء والإحصائيات المتكامل",
            font=("Arial", 14)
        ).pack()
        
        # تبويبات التنقل
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=10)
        
        # إضافة التبويبات
        self.tabview.add("تسجيل النزلاء")
        self.tabview.add("البحث والتعديل")
        self.tabview.add("الإحصائيات")
        self.tabview.add("الإعدادات")
        
        # إطارات المحتوى لكل تبويب
        self.registration_frame = GuestRegistrationFrame(
            self.tabview.tab("تسجيل النزلاء"),
            self.db_manager
        )
        self.registration_frame.pack(fill="both", expand=True)
        
        self.search_frame = SearchFrame(
            self.tabview.tab("البحث والتعديل"),
            self.db_manager
        )
        self.search_frame.pack(fill="both", expand=True)
        
        self.statistics_frame = StatisticsFrame(
            self.tabview.tab("الإحصائيات"),
            self.db_manager
        )
        self.statistics_frame.pack(fill="both", expand=True)
        
        self.settings_frame = SettingsFrame(
            self.tabview.tab("الإعدادات"),
            self.db_manager
        )
        self.settings_frame.pack(fill="both", expand=True)
        
        # شريط الحالة
        self.status_bar = ctk.CTkFrame(self, height=30)
        self.status_bar.pack(fill="x", side="bottom")
        
        self.status_label = ArabicText.create_label(
            self.status_bar,
            "جاهز - نظام إدارة بيت الشباب كريم جلول",
            font=("Arial", 10)
        )
        self.status_label.pack(side="left", padx=10)
        
        # تحديث حالة قاعدة البيانات
        self.update_status()
    
    def update_status(self):
        """تحديث شريط الحالة"""
        try:
            conn = sqlite3.connect(self.db_manager.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM guests")
            guest_count = cursor.fetchone()[0]
            conn.close()
            
            status_text = f"عدد النزلاء المسجلين: {guest_count} | نظام التشغيل: {sys.platform}"
            self.status_label.configure(text=ArabicText.reshape(status_text))
            
        except Exception as e:
            self.status_label.configure(text=f"خطأ في الاتصال بقاعدة البيانات: {str(e)}")
        
        # تحديث كل 30 ثانية
        self.after(30000, self.update_status)

def main():
    """الدالة الرئيسية لتشغيل التطبيق"""
    app = MainApplication()
    app.mainloop()

if __name__ == "__main__":
    main()