How to Run this:

1) Run Backend first:
cd app/backend/
uvicorn backend:app --reload --host 127.0.0.1 --port 8000

2) Run Frontend next (in seperate terminal):
cd app/frontend/
npm install
npm run dev

visit localhost:8000 to access the web app