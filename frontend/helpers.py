from os import getenv

def get_rabbitmq_host():
    if getenv("ENVIRONMENT").lower() == "production":
        return "rabbitmq"
    elif getenv("ENVIRONMENT").lower() == "development":
        return "localhost"
    else:
        raise ValueError(f"Unknown environment {getenv('ENVIRONMENT')}")

def get_db_host():
    if getenv("ENVIRONMENT").lower() == "production":
        return "database"
    elif getenv("ENVIRONMENT").lower() == "development":
        return "localhost"
    else:
        raise ValueError(f"Unknown environment {getenv('ENVIRONMENT')}")
