from fastapi import FastAPI

import json

from registry import actor

app = FastAPI()

app.include_router(actor.router)


@app.get("/")
async def root():
    with open("./registryfiles/trustregistry.json", "r") as tr:
        registry_file = json.load(tr)
    return registry_file


@app.get("/registry")
async def registry():
    return await root()
