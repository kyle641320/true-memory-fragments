def tax(subtotal):
    return subtotal // 10

def total(items):
    subtotal = sum(items)
    return subtotal + tax(subtotal)
