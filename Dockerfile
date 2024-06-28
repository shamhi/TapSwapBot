FROM python:3.11.4-slim

WORKDIR /app

COPY . /app

RUN apt update && apt install -y \
    wget \
    curl \
    gnupg \
    apt-transport-https \
    ca-certificates

RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list' && \
    apt update && \
    apt install -y google-chrome-stable && \
    apt clean

RUN pip3 install --upgrade pip setuptools wheel
RUN pip3 install --no-warn-script-location --no-cache-dir -r requirements.txt

CMD ["python3", "main.py", "-a", "2"]
