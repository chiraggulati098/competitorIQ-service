from clerk_backend_api import Clerk, AuthenticateRequestOptions
from fastapi import HTTPException
import dotenv
import os

dotenv.load_dotenv()

clerk_sdk = Clerk(bearer_auth=os.getenv("CLERK_SECRET_KEY"))

def authenticate_and_get_user_details(request):
    try:
        request_state = clerk_sdk.authenticate_request(
            request,
            AuthenticateRequestOptions(
                authorized_parties=["http://localhost:8000", "http://localhost:8080"],
                jwt_key=os.getenv("JWT_KEY"),
            )
        )
        if not request_state.is_authenticated:
            raise HTTPException(status=401, detail="Invalid token")
        
        user_id = request_state.payload.get("sub")
        print(f"Authenticated user ID: {user_id}")
        return {"user_id": user_id}

    except Exception as e:
        raise HTTPException(status=500, detail="Invalid credentials")