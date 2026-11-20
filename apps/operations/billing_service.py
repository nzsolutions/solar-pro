import calendar
from datetime import date, datetime

MONTH_NAME_TO_INT = {
    'january': 1, 'february': 2, 'march': 3, 'april': 4,
    'may': 5, 'june': 6, 'july': 7, 'august': 8,
    'september': 9, 'october': 10, 'november': 11, 'december': 12
}

MONTH_INT_TO_NAME = {v: k.capitalize() for k, v in MONTH_NAME_TO_INT.items()}

ALL_MONTHS = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
]


def parse_date_safely(d):
    if not d:
        return None
    if isinstance(d, date):
        return d
    try:
        return datetime.strptime(str(d).strip(), '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None


def calculate_billing_dates(start_date, end_date, frequency, billing_day, billing_month=None):
    """
    Calculates valid billing dates between start_date and end_date.
    Clamps day to the last valid day of the month (e.g. 31st on a 30-day month, Feb leap year 29, etc.).
    Returns list of tuples: [(date_obj, period_label), ...]
    """
    s_date = parse_date_safely(start_date)
    e_date = parse_date_safely(end_date)
    if not s_date or not e_date or e_date < s_date:
        return []

    try:
        b_day = int(billing_day)
    except (ValueError, TypeError):
        b_day = 1
    b_day = max(1, min(31, b_day))

    freq = (frequency or '').strip().capitalize()
    results = []

    if freq == 'Monthly':
        cur_year = s_date.year
        cur_month = s_date.month
        end_year = e_date.year
        end_month = e_date.month

        while (cur_year < end_year) or (cur_year == end_year and cur_month <= end_month):
            max_day = calendar.monthrange(cur_year, cur_month)[1]
            actual_day = min(b_day, max_day)
            cand_date = date(cur_year, cur_month, actual_day)

            if s_date <= cand_date <= e_date:
                period_str = f"Monthly ({cand_date.strftime('%B %Y')})"
                results.append((cand_date, period_str))

            if cur_month == 12:
                cur_month = 1
                cur_year += 1
            else:
                cur_month += 1

    elif freq == 'Quarterly':
        # Quarterly billing: generates once every quarter.
        # Starting from the agreement start month, stepping 3 months at a time across period.
        cur_year = s_date.year
        cur_month = s_date.month

        while True:
            if (cur_year > e_date.year) or (cur_year == e_date.year and cur_month > e_date.month):
                break

            max_day = calendar.monthrange(cur_year, cur_month)[1]
            actual_day = min(b_day, max_day)
            cand_date = date(cur_year, cur_month, actual_day)

            if s_date <= cand_date <= e_date:
                q_num = ((cur_month - 1) // 3) + 1
                period_str = f"Q{q_num} {cur_year} ({cand_date.strftime('%B %Y')})"
                results.append((cand_date, period_str))

            cur_month += 3
            if cur_month > 12:
                cur_year += (cur_month - 1) // 12
                cur_month = ((cur_month - 1) % 12) + 1

    elif freq == 'Yearly':
        t_month = 1
        if billing_month:
            b_m_str = str(billing_month).strip().lower()
            if b_m_str in MONTH_NAME_TO_INT:
                t_month = MONTH_NAME_TO_INT[b_m_str]
            elif b_m_str.isdigit() and 1 <= int(b_m_str) <= 12:
                t_month = int(b_m_str)

        for y in range(s_date.year, e_date.year + 1):
            max_day = calendar.monthrange(y, t_month)[1]
            actual_day = min(b_day, max_day)
            cand_date = date(y, t_month, actual_day)

            if s_date <= cand_date <= e_date:
                m_name = MONTH_INT_TO_NAME.get(t_month, '')
                period_str = f"Yearly ({m_name} {y})"
                results.append((cand_date, period_str))

    return results


def sync_project_billing_notifications(project):
    """
    Synchronizes ProjectBillingNotification records for the given Project.
    Avoids duplicate notifications when project is saved multiple times.
    """
    from apps.operations.models import ProjectBillingNotification

    if not project or project.agreement != 'Yes':
        ProjectBillingNotification.objects.filter(project=project, is_sent=False).delete()
        return []

    s_date = parse_date_safely(project.agreement_start_date)
    e_date = parse_date_safely(project.agreement_end_date)
    freq = project.billing_frequency
    b_day = project.billing_day or 1
    b_month = project.billing_month

    if not s_date or not e_date or e_date < s_date:
        return []

    scheduled = calculate_billing_dates(s_date, e_date, freq, b_day, b_month)
    scheduled_dates = {d for d, _ in scheduled}

    # Delete unsent notifications that are no longer in scheduled_dates
    ProjectBillingNotification.objects.filter(
        project=project,
        is_sent=False
    ).exclude(notification_date__in=scheduled_dates).delete()

    existing_notifs = {
        n.notification_date: n
        for n in ProjectBillingNotification.objects.filter(project=project)
    }

    created_or_updated = []
    for cand_date, period_str in scheduled:
        if cand_date in existing_notifs:
            notif = existing_notifs[cand_date]
            if notif.billing_period != period_str:
                notif.billing_period = period_str
                notif.save(update_fields=['billing_period', 'updated_at'])
            created_or_updated.append(notif)
        else:
            notif = ProjectBillingNotification.objects.create(
                project=project,
                notification_date=cand_date,
                billing_period=period_str,
                title=f"Billing Notification: {project.client_name}",
                message=f"Scheduled billing on {cand_date.strftime('%d %b %Y')} for project '{project.project_name or project.client_name}' ({period_str}).",
                is_sent=False
            )
            created_or_updated.append(notif)

    # Set project's next/first upcoming bill_date
    today = date.today()
    future_or_current = [d for d, _ in scheduled if d >= today]
    if future_or_current:
        next_bill = future_or_current[0]
    elif scheduled:
        next_bill = scheduled[0][0]
    else:
        next_bill = None

    if next_bill and project.bill_date != next_bill:
        project.bill_date = next_bill
        project.save(update_fields=['bill_date', 'updated_at'])

    return created_or_updated
