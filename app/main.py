from fastapi import FastAPI
from routers import issuer, schema, verifier
from admin.governance import schemas, credential_definitions
from admin.governance.multitenant_wallet import wallet
from admin.governance import dids
from admin.governance.wallet import wallets_admin

app = FastAPI()


app.include_router(dids.router)
app.include_router(schema.router)
app.include_router(schemas.router)
app.include_router(credential_definitions.router)
app.include_router(wallet.router)
app.include_router(verifier.router)
app.include_router(issuer.router)
app.include_router(wallets_admin.router)


@app.get("/")
async def root():
    return {"message": "Hi, and welcome to the Aries Cloud API."}
