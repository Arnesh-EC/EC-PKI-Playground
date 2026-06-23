import uvicorn


def main() -> None:
    uvicorn.run("app.main:app", reload=True)
