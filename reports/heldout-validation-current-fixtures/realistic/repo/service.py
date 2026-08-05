from dataclasses import dataclass

DEFAULT_ROLE = "user"

@dataclass
class User:
    name: str

def normalize(user):
    return user.name.strip().lower()
