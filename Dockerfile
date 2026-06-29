FROM python:3.11-slim

WORKDIR /app

COPY requirements-zth.txt .
RUN pip install --no-cache-dir --pre -r requirements-zth.txt

COPY bot/zerotoherobtc.py .
COPY bot/redeem_zth.py .

CMD ["python", "zerotoherobtc.py"]
