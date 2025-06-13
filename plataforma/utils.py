import random

def generate_token():
    return ''.join(random.choices('0123456789', k=6))
