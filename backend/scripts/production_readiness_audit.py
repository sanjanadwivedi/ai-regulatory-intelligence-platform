import os
import sys

def check_production_readiness():
    errors = []
    warnings = []
    
    # 1. Environment Verification
    env = os.getenv("ENVIRONMENT", "development")
    if env != "production":
        warnings.append(f"ENVIRONMENT is not 'production' (current: {env}).")
        
    secret_key = os.getenv("SECRET_KEY", "super-secret-key-change-in-production")
    if secret_key == "super-secret-key-change-in-production" or len(secret_key) < 32:
        errors.append("SECRET_KEY is insecure, missing, or uses default fallback.")
        
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    if "localhost" in frontend_url or "127.0.0.1" in frontend_url:
        warnings.append(f"FRONTEND_URL contains localhost ({frontend_url}).")

    # 2. Inspect backend/app/main.py for Security Headers / CORS
    try:
        with open("app/main.py", "r", encoding="utf-8") as f:
            main_content = f.read()
            if 'allow_origins=["*"]' in main_content or "allow_origins=['*']" in main_content:
                errors.append("Unsafe CORS: allow_origins=['*'] is present in main.py")
            if "X-Content-Type-Options" not in main_content:
                warnings.append("Security headers (e.g. X-Content-Type-Options) missing in main.py")
            if "/health/ready" not in main_content:
                warnings.append("Missing GET /health/ready endpoint in main.py")
            if "localhost" in main_content and "allow_origins" in main_content:
                warnings.append("Hard-coded localhost origin found in CORS middleware.")
    except FileNotFoundError:
        errors.append("Could not read app/main.py")

    # 3. Inspect Frontend configuration
    try:
        with open("../frontend/src/services/api.ts", "r", encoding="utf-8") as f:
            api_ts = f.read()
            if "http://localhost" in api_ts:
                warnings.append("Frontend api.ts contains hard-coded 'http://localhost'")
    except FileNotFoundError:
        warnings.append("Could not read frontend/src/services/api.ts")

    # 4. Check for hard-coded credentials in config.py
    try:
        with open("app/core/config.py", "r", encoding="utf-8") as f:
            config_content = f.read()
            if 'GEMINI_API_KEY = "AIza' in config_content:
                errors.append("Hard-coded GEMINI_API_KEY detected in config.py")
    except FileNotFoundError:
        errors.append("Could not read app/core/config.py")

    # 5. Check Gitignore
    try:
        with open("../.gitignore", "r", encoding="utf-8") as f:
            gitignore = f.read()
            if ".env" not in gitignore:
                errors.append(".env missing from .gitignore")
            if "*.sqlite" not in gitignore and "*.db" not in gitignore:
                errors.append("SQLite databases missing from .gitignore")
    except FileNotFoundError:
        errors.append("Could not read ../.gitignore")

    print("=" * 60)
    print("PRODUCTION READINESS AUDIT")
    print("=" * 60)

    if not errors and not warnings:
        print("[PASS] System appears production-ready.")
        return 0

    if errors:
        print("\n[ERRORS] Must be fixed before production:")
        for e in errors:
            print(f"  [X] {e}")
            
    if warnings:
        print("\n[WARNINGS] Should be addressed:")
        for w in warnings:
            print(f"  [!] {w}")

    return 1 if errors else 0

if __name__ == "__main__":
    sys.exit(check_production_readiness())
