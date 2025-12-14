import jwt
import datetime

# Secret from kong.yml
SECRET = "This_Is_A_Symmetric_Secret_Used_To_Verify_The_JWT_Signature_Replace_Me_In_Production"
ISSUER = "platform-jwt-issuer"

def generate_token():
    payload = {
        "iss": ISSUER,
        "sub": "verification-dashboard-user",
        "name": "Admin User",
        "role": "admin",
        "exp": datetime.datetime.utcnow() + datetime.timedelta(days=365) # Long lived for dev
    }
    
    token = jwt.encode(payload, SECRET, algorithm="HS256")
    print(token)

if __name__ == "__main__":
    generate_token()
