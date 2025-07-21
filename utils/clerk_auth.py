from clerk_backend_api import Clerk, AuthenticateRequestOptions
from fastapi import HTTPException
import dotenv
import os

dotenv.load_dotenv()
CLERK_SECRET_KEY = os.getenv("CLERK_SECRET_KEY")

clerk_sdk = Clerk(bearer_auth=CLERK_SECRET_KEY)

def authenticate_and_get_user_details(request):
    try:
        request_state = clerk_sdk.authenticate_request(
            request,
            AuthenticateRequestOptions(
                authorized_parties=["http://localhost:8000", "http://localhost:8080", "https://competitor-iq-insights-ai.vercel.app"],
                jwt_key=os.getenv("JWT_KEY"),
            )
        )
        if not request_state.is_authenticated:
            raise HTTPException(status=401, detail="Invalid token")
        
        user_id = request_state.payload.get("sub")
        return {"user_id": user_id}

    except Exception as e:
        raise HTTPException(status=500, detail="Invalid credentials")

def get_user_mails():
    user_details = clerk_sdk.users.list()

    return {
        user.id: user.email_addresses[0].email_address
        for user in user_details
        if user.email_addresses  
    }