import contextlib
import logging
import os
from typing import Union

import fastapi
from azure.ai.projects.aio import AIProjectClient
from azure.identity import AzureDeveloperCliCredential, ManagedIdentityCredential, AzureCliCredential
from dotenv import load_dotenv
from fastapi.staticfiles import StaticFiles

from .shared import globals

logger = logging.getLogger("azureaiapp")
logger.setLevel(logging.INFO)


@contextlib.asynccontextmanager
async def lifespan(app: fastapi.FastAPI):
    azure_credential: Union[AzureDeveloperCliCredential, ManagedIdentityCredential, AzureCliCredential]
    if not os.getenv("RUNNING_IN_PRODUCTION"):
        if tenant_id := os.getenv("AZURE_TENANT_ID"):
            logger.info("Using AzureCliCredential with tenant_id %s", tenant_id)
            azure_credential = AzureCliCredential(tenant_id=tenant_id)
        else:
            logger.info("Using AzureCliCredential")
            azure_credential = AzureCliCredential()
    else:
        # User-assigned identity was created and set in api.bicep
        user_identity_client_id = os.getenv("AZURE_CLIENT_ID")
        logger.info("Using ManagedIdentityCredential with client_id %s", user_identity_client_id)
        azure_credential = ManagedIdentityCredential(client_id=user_identity_client_id)

    project = AIProjectClient.from_connection_string(
        credential=azure_credential,
        conn_str=os.environ["AZURE_AIPROJECT_CONNECTION_STRING"],
    )

    chat = await project.inference.get_chat_completions_client()
    globals["project"] = project
    globals["chat"] = chat
    globals["chat_model"] = os.environ["AZURE_AI_CHAT_DEPLOYMENT_NAME"]

    yield

    await project.close()
    await chat.close()


def create_app():
    if not os.getenv("RUNNING_IN_PRODUCTION"):
        logger.info("Loading .env file")
        load_dotenv(override=True)

    app = fastapi.FastAPI(lifespan=lifespan)
    app.mount("/static", StaticFiles(directory="api/static"), name="static")

    from . import routes  # noqa

    app.include_router(routes.router)

    return app
