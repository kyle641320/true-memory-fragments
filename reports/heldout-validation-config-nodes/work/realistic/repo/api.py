from service import normalize, User

def handler(raw):
    return normalize(User(raw))
