FROM python:alpine

WORKDIR /app

COPY requirements.txt /app/

RUN pip install -r requirements.txt

COPY *.py /app/

ENV TELEGRAM_GPT_DATA_DIR=/data
RUN mkdir -p /data

ENTRYPOINT ["python", "telegram-gpt.py"]
