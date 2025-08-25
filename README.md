## Quant Futures System (Binance USDT-M)

Bu depo, Binance USDT-M Futures üzerinde risk-ayarlı getiri odaklı bir sistemin modüler mimarisini içerir. Kart A (Symbol Meta & Data Core) tamamlanmıştır: REST istemci, cache, OHLCV/funding veri çekimi ve veri hijyeni araçları.

### Kurulum

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### Hızlı Başlangıç

Örnek sembol meta ve OHLCV veri çekimi:

```bash
python scripts/bootstrap_data.py --symbols BTCUSDT ETHUSDT --interval 15m --days 7
```

API anahtarı gerekmez (public endpointler). Kaldıraç/maintenance tier verisi için `.env` ile anahtarlar verilebilir.

### Yapı (şimdilik)
- `src/quant_futures/data`
- `src/quant_futures/utils`
- `scripts/bootstrap_data.py`

Kartlar: A→I sırasıyla genişleyecek.
