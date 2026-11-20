import re
import json

def _to_float(val):
    if val is None:
        return None
    val_str = str(val).strip()
    # Strip common units and symbols: %, °C, kW, kWh, V, A, etc.
    val_str = re.sub(r'[^\d.\-+]', '', val_str)
    try:
        return float(val_str)
    except (ValueError, TypeError):
        return None

def check_single_condition(submitted_val, operator, flag_val, q_type='text'):
    """
    Evaluates whether a single submitted value matches a flag condition.
    Returns: bool (True if flagged)
    """
    if submitted_val is None or str(submitted_val).strip() == '':
        return False

    s_str = str(submitted_val).strip()
    f_str = str(flag_val).strip()
    op = (operator or 'equals').lower().strip()

    # Try numeric comparison if operator is numeric or question is number
    num_s = _to_float(s_str)
    num_f = _to_float(f_str)

    if op in ('>', 'gt', 'greater_than') and num_s is not None and num_f is not None:
        return num_s > num_f
    if op in ('<', 'lt', 'less_than') and num_s is not None and num_f is not None:
        return num_s < num_f
    if op in ('>=', 'gte', 'greater_than_or_equal') and num_s is not None and num_f is not None:
        return num_s >= num_f
    if op in ('<=', 'lte', 'less_than_or_equal') and num_s is not None and num_f is not None:
        return num_s <= num_f

    # Normalize text / yes-no / ok-nok
    s_low = s_str.lower()
    f_low = f_str.lower()

    # Synonym mapping for Yes/No & OK/NOK
    is_neg_submitted = s_low in ('no', 'nok', 'false', 'n')
    is_neg_flag = f_low in ('no', 'nok', 'false', 'n')
    is_pos_submitted = s_low in ('yes', 'ok', 'true', 'y')
    is_pos_flag = f_low in ('yes', 'ok', 'true', 'y')

    if op in ('equals', '==', '=', 'eq'):
        if is_neg_flag and is_neg_submitted:
            return True
        if is_pos_flag and is_pos_submitted:
            return True
        if num_s is not None and num_f is not None:
            return num_s == num_f
        return s_low == f_low

    if op in ('not_equals', '!=', '<>', 'neq'):
        if is_neg_flag:
            return not is_neg_submitted
        if is_pos_flag:
            return not is_pos_submitted
        if num_s is not None and num_f is not None:
            return num_s != num_f
        return s_low != f_low

    if op in ('contains', 'includes', 'contain'):
        return f_low in s_low

    # Default fallback
    return s_low == f_low

def format_condition_description(operator, flag_val):
    op = (operator or 'equals').lower().strip()
    if op in ('>', 'gt', 'greater_than'):
        return f"> {flag_val}"
    if op in ('<', 'lt', 'less_than'):
        return f"< {flag_val}"
    if op in ('>=', 'gte', 'greater_than_or_equal'):
        return f">= {flag_val}"
    if op in ('<=', 'lte', 'less_than_or_equal'):
        return f"<= {flag_val}"
    if op in ('!=', '<>', 'neq', 'not_equals'):
        return f"!= {flag_val}"
    if op in ('contains', 'includes'):
        return f"Contains \"{flag_val}\""
    return f"Equals \"{flag_val}\""

def evaluate_form_submission(form_schema, submission_data):
    """
    Evaluates submitted answers against configured flags in form_schema.
    Returns:
        (is_flagged: bool, flagged_details: list of dicts)
        Each dict has: {'question': str, 'answer': str, 'flag_condition': str}
    """
    if isinstance(form_schema, str):
        try:
            form_schema = json.loads(form_schema)
        except Exception:
            form_schema = {}

    if not isinstance(form_schema, dict):
        return False, []

    flags = form_schema.get('flags', [])
    if not flags or not isinstance(flags, list):
        return False, []

    if isinstance(submission_data, str):
        try:
            submission_data = json.loads(submission_data)
        except Exception:
            submission_data = {}

    if not isinstance(submission_data, dict):
        return False, []

    flagged_details = []
    seen_flag_keys = set()

    # Build question lookup map from flags
    # Key: normalized question name
    flag_rules_by_q = {}
    for flag in flags:
        if not isinstance(flag, dict):
            continue
        q_name = (flag.get('question') or flag.get('name') or '').strip()
        if not q_name:
            continue
        flag_rules_by_q.setdefault(q_name.lower(), []).append(flag)

    if not flag_rules_by_q:
        return False, []

    # 1. Check Matrix format: submission_data.get('sections', []) -> rows -> answers
    sections = submission_data.get('sections', [])
    if isinstance(sections, list):
        for sec in sections:
            if not isinstance(sec, dict):
                continue
            rows = sec.get('rows', [])
            if not isinstance(rows, list):
                continue
            for r in rows:
                if not isinstance(r, dict):
                    continue
                r_name = (r.get('name') or r.get('label') or '').strip()
                r_name_low = r_name.lower()
                matching_rules = flag_rules_by_q.get(r_name_low) or []
                if not matching_rules:
                    continue

                answers = r.get('answers') or r.get('values') or {}
                if isinstance(answers, dict):
                    for col_name, val in answers.items():
                        if val is None or str(val).strip() == '':
                            continue
                        for rule in matching_rules:
                            op = rule.get('operator', 'equals')
                            target_val = rule.get('value', '')
                            q_type = rule.get('question_type', 'text')
                            if check_single_condition(val, op, target_val, q_type):
                                display_q = f"{r_name} ({col_name})" if col_name else r_name
                                item_key = (display_q, str(val), op, str(target_val))
                                if item_key not in seen_flag_keys:
                                    seen_flag_keys.add(item_key)
                                    flagged_details.append({
                                        'question': display_q,
                                        'answer': str(val),
                                        'flag_condition': format_condition_description(op, target_val)
                                    })
                elif isinstance(answers, (str, int, float)):
                    val = answers
                    for rule in matching_rules:
                        op = rule.get('operator', 'equals')
                        target_val = rule.get('value', '')
                        q_type = rule.get('question_type', 'text')
                        if check_single_condition(val, op, target_val, q_type):
                            item_key = (r_name, str(val), op, str(target_val))
                            if item_key not in seen_flag_keys:
                                seen_flag_keys.add(item_key)
                                flagged_details.append({
                                    'question': r_name,
                                    'answer': str(val),
                                    'flag_condition': format_condition_description(op, target_val)
                                })

    # 2. Check Flat formats: fields, values, inspection_details, or top-level keys
    flat_sources = []
    for key in ('values', 'fields', 'answers', 'inspection_details'):
        sub_part = submission_data.get(key)
        if isinstance(sub_part, dict):
            flat_sources.append(sub_part)

    # Also top-level key-values if not reserved keys
    top_level = {k: v for k, v in submission_data.items() if k not in (
        'sections', 'columns', 'photo_evidence', 'gps_coordinates', 'timestamps',
        'values', 'fields', 'answers', 'inspection_details', 'field_photos', 'raw_data'
    )}
    if top_level:
        flat_sources.append(top_level)

    for source_dict in flat_sources:
        for k, val in source_dict.items():
            if val is None or str(val).strip() == '':
                continue
            k_clean = str(k).strip()
            k_low = k_clean.lower()
            matching_rules = flag_rules_by_q.get(k_low) or []
            if not matching_rules:
                # Also check if k is a subpart or field label
                for q_low, rules in flag_rules_by_q.items():
                    if q_low == k_low:
                        matching_rules = rules
                        break
            for rule in matching_rules:
                op = rule.get('operator', 'equals')
                target_val = rule.get('value', '')
                q_type = rule.get('question_type', 'text')
                if check_single_condition(val, op, target_val, q_type):
                    item_key = (k_clean, str(val), op, str(target_val))
                    if item_key not in seen_flag_keys:
                        seen_flag_keys.add(item_key)
                        flagged_details.append({
                            'question': rule.get('question') or k_clean,
                            'answer': str(val),
                            'flag_condition': format_condition_description(op, target_val)
                        })

    return len(flagged_details) > 0, flagged_details
