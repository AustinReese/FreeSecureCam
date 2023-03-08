from os import getenv

def get_rabbitmq_host():
    match getenv("ENVIRONMENT").lower():
        case "production":
            return "rabbitmq"
        case "development":
            return "localhost"
        case _:
            raise ValueError(f"Unknown environment {getenv('ENVIRONMENT')}")

def get_db_host():
    match getenv("ENVIRONMENT").lower():
        case "production":
            return "database"
        case "development":
            return "localhost"
        case _:
            raise ValueError(f"Unknown environment {getenv('ENVIRONMENT')}")

def get_ip_to_bind(socket):
    match getenv("ENVIRONMENT").lower():
        case "production":
            return socket.gethostname()
        case "development":
            return "0.0.0.0"
        case _:
            raise ValueError(f"Unknown environment {getenv('ENVIRONMENT')}")
