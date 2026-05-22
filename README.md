# Log Analyzer

## Run

From the repo root, install dependencies and start both apps:

```powershell
cd backend; python -m pip install -r requirements.txt; cd ..\frontend; npm install; npm run dev; cd ..\backend; python -m uvicorn main:app --reload --port 8000
```

If you prefer a cleaner local setup, run the backend and frontend in separate terminals:

```powershell
cd backend
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```

```powershell
cd frontend
npm install
npm run dev
```
