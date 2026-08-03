FROM python:3.12.13-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       make texlive-latex-base texlive-latex-extra texlive-fonts-recommended lmodern \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /artifact
COPY requirements-lock.txt ./requirements-lock.txt
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements-lock.txt
COPY . .
CMD ["make", "reproduce"]
