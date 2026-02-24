from fastapi import FastAPI, Request

app = FastAPI()

@app.get("/")
async def root():
    return {"status": "ok"}

@app.post("/telegram")
async def telegram_webhook(request: Request):
    update = await request.json()
    print(update)
    return {"ok": True}
