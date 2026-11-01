python -m venv .venv
.venv/Scripts/pip install -r requirements.txt
cd frontend && npm install && npm run build && cd ..
.venv/Scripts/python run.py