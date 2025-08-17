## Malzeme Takip Sistemi

Modern, modüler ve genişletilebilir bir masaüstü uygulaması. Tkinter tabanlı arayüz ile projeler ve malzeme listeleri yönetilir; Excel/CSV içe/dışa aktarım, çoklu seçim ve panoya kopyalama desteklenir. Veriler JSON olarak saklanır.

### Özellikler
- Proje ve malzeme CRUD
- Filtreleme (Müşteri, Proje No, FAT tarih aralığı, genel arama)
- Excel/CSV rapor dışa aktarımı ve Excel’den içe aktarım
- Çoklu seçim ile panoya kopyalama (opsiyonel `pyperclip`)
- Oturum ayarları (sütun genişlikleri, tema için altyapı)
- JSON veri kaydetme/yükleme

### Kurulum
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Çalıştırma
```bash
python app.py
```

Excel desteği için `pandas` ve `openpyxl` kurulu olmalıdır (requirements içerir). Panoya kopyalama için `pyperclip` önerilir.

### Proje Yapısı
```
app.py                  # giriş noktası
malzeme/
  __init__.py          # sabitler ve meta
  models.py            # Project / Material modelleri
  storage.py           # JSON/Excel depolama
  controller.py        # iş mantığı / filtreleme
  ui.py                # Tkinter arayüzü
```

### Notlar
- Uygulama kapanırken veriler `data.json` dosyasına kaydedilir.
- Sütun genişlikleri `settings.json` içinde saklanır.
