from dataclasses import dataclass

@dataclass
class User:
    name: str

def normalize(user):
    return user.name.strip().lower()
