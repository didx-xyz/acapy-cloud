from admin import admin
from dependencies import get_query_token, get_token_header
from fastapi import Depends, FastAPI
from routers import governance, holder, issuer, schema, verifier, wallet

app = FastAPI()


app.include_router(schema.router)
app.include_router(wallet.router)
app.include_router(verifier.router)
# app.include_router(
#     admin.router,
#     prefix="/admin",
#     tags=["admin"],
#     dependencies=[Depends(get_token_header)],
#     responses={418: {"description": "I'm a teapot"}},
# )

app.include_router(issuer.router)


@app.get("/")
async def root():
    return {"message": "Hi, and welcome to the Aries Cloud API."}
