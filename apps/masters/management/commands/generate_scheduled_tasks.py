"""
Management command to run automated task generation for all active activity schedules.
Usage:
    python manage.py generate_scheduled_tasks [--days 60] [--company 1]
"""
from django.core.management.base import BaseCommand
from apps.masters.schedule_service import ActivityScheduleService


class Command(BaseCommand):
    help = 'Automatically generates task instances for active recurring activity schedules without duplication.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=60,
            help='Lookahead horizon in days (default: 60 days)'
        )
        parser.add_argument(
            '--company',
            type=int,
            default=None,
            help='Specific company_id to filter by (optional)'
        )

    def handle(self, *args, **options):
        days = options['days']
        company_id = options['company']

        self.stdout.write(self.style.NOTICE(
            f'Starting automatic task generation (horizon={days} days, company={company_id or "All"})...'
        ))

        result = ActivityScheduleService.generate_all_active_schedules(
            horizon_days=days,
            company_id=company_id
        )

        tasks_created = result.get('tasks_created', 0)
        schedules_processed = result.get('schedules_processed', 0)

        self.stdout.write(self.style.SUCCESS(
            f'Successfully generated {tasks_created} task(s) '
            f'across {schedules_processed} active schedule(s).'
        ))
