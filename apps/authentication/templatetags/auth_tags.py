from django import template

register = template.Library()

@register.filter
def can_see(allowed_modules, key):
    """
    Returns True if allowed_modules is None (admin) or key is in allowed_modules (employee).
    """
    if allowed_modules is None:
        return True
    if isinstance(allowed_modules, (list, tuple, set)):
        return key in allowed_modules
    return False

@register.filter
def has_any(allowed_modules, keys_csv):
    """
    Returns True if allowed_modules is None or any key in the comma-separated string is allowed.
    """
    if allowed_modules is None:
        return True
    keys = [k.strip() for k in keys_csv.split(',') if k.strip()]
    if not isinstance(allowed_modules, (list, tuple, set)):
        return False
    return any(k in allowed_modules for k in keys)

@register.filter
def get_initials(name):
    if not name:
        return 'U'
    parts = str(name).strip().split()
    if len(parts) >= 2:
        return f"{parts[0][0]}{parts[1][0]}".upper()
    elif len(parts) == 1 and parts[0]:
        return parts[0][:2].upper()
    return 'U'
