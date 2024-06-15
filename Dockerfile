FROM python:3.10.11-alpine3.18

WORKDIR /app

COPY . /app

RUN pip3 install --upgrade pip setuptools wheel
RUN pip3 install --no-warn-script-location --no-cache-dir -r requirements.txt

RUN apk add --no-cache firefox

CMD ["python3", "main.py", "-a", "2"]
