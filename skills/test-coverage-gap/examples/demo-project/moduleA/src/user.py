# Synthetic source for path matching; no business code is executed.
def format_user(identifier):
    return {
        'id': identifier,
        'label': str(identifier),
    }
