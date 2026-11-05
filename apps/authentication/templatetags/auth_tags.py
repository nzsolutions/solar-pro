from django import template
import fnmatch

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

@register.simple_tag(takes_context=True)
def route_is(context, patterns_str):
    """
    Returns True if current resolver_match url_name matches any of the given patterns.
    Supports wildcards like 'admin_departments_*' or comma-separated patterns: 'admin_smtp_*,admin_sites_*'.
    Also checks request.path if pattern starts with '/'.
    """
    request = context.get('request')
    if not request:
        return False
    
    current_name = getattr(request.resolver_match, 'url_name', '') or ''
    current_path = getattr(request, 'path', '') or ''

    patterns = [p.strip() for p in patterns_str.split(',') if p.strip()]
    for pat in patterns:
        if pat.startswith('/'):
            if current_path == pat or current_path.startswith(pat + '/'):
                return True
        elif '*' in pat:
            if fnmatch.fnmatch(current_name, pat):
                return True
        else:
            if current_name == pat:
                return True
    return False
