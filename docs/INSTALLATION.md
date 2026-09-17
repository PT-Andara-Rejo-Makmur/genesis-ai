# Instalasi

Gunakan Python 3.12 dan Git. Provider credential, PostgreSQL, dan pgvector tidak diperlukan untuk menjalankan service foundation atau test suite.

## Windows PowerShell

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev,frameworks]"
Copy-Item .env.example .env
```

## Linux/macOS

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev,frameworks]'
cp .env.example .env
```

Jangan menyimpan `.env`, service token, atau provider key ke Git.
