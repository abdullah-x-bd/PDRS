FROM python:3.13-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cargo make texlive-latex-base texlive-latex-extra \
    texlive-fonts-recommended lmodern bibtex2html poppler-utils zip \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /artifact
COPY requirements-lock.txt .
RUN python -m pip install --no-cache-dir -r requirements-lock.txt asn1tools dd
COPY . .
CMD ["make", "reproduce-full"]
