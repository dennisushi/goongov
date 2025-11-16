# Running Frontend and Backend Separately

This guide explains how to run the frontend and backend in separate terminals.

## Option 1: Using the Provided Scripts (Recommended)

### Terminal 1 - Backend (Flask API)
```bash
cd /home/dennisushi/personal/hackthon-2025/goongov
./run_backend.sh
```

This will start the Flask backend server on `http://localhost:5000`

### Terminal 2 - Frontend (Development Server)
```bash
cd /home/dennisushi/personal/hackthon-2025/goongov
./run_frontend.sh
```

This will start a simple HTTP server on `http://localhost:3000`

Then open your browser to: `http://localhost:3000/frontend/index_standalone.html`

## Option 2: Manual Commands

### Terminal 1 - Backend
```bash
cd /home/dennisushi/personal/hackthon-2025/goongov
python -m flask --app backend.app run --port 5000 --debug
```

### Terminal 2 - Frontend
```bash
cd /home/dennisushi/personal/hackthon-2025/goongov/frontend
python3 -m http.server 3000
```

Then open: `http://localhost:3000/index_standalone.html`

## Option 3: Using Flask for Both (Current Setup)

If you want to keep using Flask to serve both frontend and backend:

```bash
cd /home/dennisushi/personal/hackthon-2025/goongov
python -m flask --app backend.app run --port 5000 --debug
```

Then open: `http://localhost:5000`

## Configuration

### Changing Backend Port

If you want to run the backend on a different port (e.g., 8000):

1. Update `run_backend.sh`:
   ```bash
   python -m flask --app backend.app run --port 8000 --debug
   ```

2. Update `frontend/index_standalone.html`:
   ```javascript
   window.API_BASE_URL = 'http://localhost:8000';
   ```

### Changing Frontend Port

If you want to run the frontend on a different port (e.g., 8080):

1. Update `run_frontend.sh`:
   ```bash
   python3 -m http.server 8080
   ```

2. Access at: `http://localhost:8080/index_standalone.html`

## Troubleshooting

### CORS Errors

If you see CORS errors when running separately, make sure:
1. `flask-cors` is installed: `pip install flask-cors`
2. CORS is enabled in `backend/app.py` (it should be by default)

### API Connection Issues

If the frontend can't connect to the backend:
1. Check that the backend is running on the correct port
2. Verify `window.API_BASE_URL` in `index_standalone.html` matches your backend URL
3. Check browser console for error messages

### Port Already in Use

If you get "port already in use" errors:
- Backend: Change port in `run_backend.sh` or use `--port` flag
- Frontend: Change port in `run_frontend.sh` or use a different port number

