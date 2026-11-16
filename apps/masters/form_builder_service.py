import json
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from apps.masters.models import (
    ActivityMaster,
    ActivityFormConfiguration,
    ActivityFormField,
    ActivityFormFieldOption,
    ActivityFormPhotoSetting,
    ActivityFormValidationRule,
)
from apps.dynamic_forms.models import DynamicForm


class ActivityFormService:
    """
    Service handling Dynamic Activity Form Builder persistence,
    serialization, pre-built templates, and business exception evaluation.
    """

    @staticmethod
    def get_or_create_form_config(activity):
        """
        Retrieves existing ActivityFormConfiguration or initializes a default one.
        """
        form_config = ActivityFormConfiguration.objects.filter(activity=activity).first()
        if not form_config:
            form_config = ActivityFormConfiguration.objects.create(
                activity=activity,
                form_title=f"{activity.activity_title} Checklist Form",
                description=activity.description or f"Standard inspection and maintenance form for {activity.activity_title}",
                company_id=activity.company_id,
                is_active=True
            )
            ActivityFormPhotoSetting.objects.create(
                form_config=form_config,
                enable_photo_capture=activity.photo_required,
                before_photo_required=activity.photo_required,
                after_photo_required=activity.photo_required,
                optional_photo=False,
                photo_instructions="Direct camera capture required for verification evidence.",
                capture_timestamp_required=True,
                submission_timestamp_required=True,
                gps_coordinates_required=True,
            )
        return form_config

    @staticmethod
    def form_to_dict(form_config):
        """
        Serializes an ActivityFormConfiguration into a clean dictionary/JSON payload.
        """
        photo_setting = getattr(form_config, 'photo_settings', None)
        if not photo_setting:
            photo_setting = ActivityFormPhotoSetting.objects.filter(form_config=form_config).first()

        fields_data = []
        fields_qs = form_config.fields.filter(is_active=True).order_by('field_order', 'id')

        for f in fields_qs:
            options_data = [
                {
                    'id': opt.id,
                    'label': opt.option_label,
                    'value': opt.option_value,
                    'display_order': opt.display_order,
                    'is_default': opt.is_default
                }
                for opt in f.options.all().order_by('display_order', 'id')
            ]

            rules_data = [
                {
                    'id': r.id,
                    'rule_type': r.rule_type,
                    'rule_name': r.rule_name,
                    'condition_operator': r.condition_operator or 'equals',
                    'expected_value': r.expected_value or '',
                    'acceptable_values': r.acceptable_values if isinstance(r.acceptable_values, list) else [],
                    'min_value': float(r.min_value) if r.min_value is not None else None,
                    'max_value': float(r.max_value) if r.max_value is not None else None,
                    'error_message': r.error_message or '',
                    'is_active': r.is_active
                }
                for r in f.validation_rules.filter(is_active=True)
            ]

            fields_data.append({
                'id': f.id,
                'field_label': f.field_label,
                'field_type': f.field_type,
                'placeholder': f.placeholder or '',
                'help_text': f.help_text or '',
                'is_required': f.is_required,
                'field_order': f.field_order,
                'settings': f.settings or {},
                'options': options_data,
                'validation_rules': rules_data
            })

        return {
            'id': form_config.id,
            'activity_id': form_config.activity_id,
            'activity_title': form_config.activity.activity_title if form_config.activity else '',
            'activity_category': form_config.activity.activity_category if form_config.activity else 'Maintenance',
            'form_title': form_config.form_title,
            'description': form_config.description or '',
            'is_active': form_config.is_active,
            'photo_settings': {
                'enable_photo_capture': photo_setting.enable_photo_capture if photo_setting else False,
                'before_photo_required': photo_setting.before_photo_required if photo_setting else False,
                'after_photo_required': photo_setting.after_photo_required if photo_setting else False,
                'optional_photo': photo_setting.optional_photo if photo_setting else True,
                'photo_instructions': photo_setting.photo_instructions if photo_setting else '',
                'capture_timestamp_required': photo_setting.capture_timestamp_required if photo_setting else True,
                'submission_timestamp_required': photo_setting.submission_timestamp_required if photo_setting else True,
                'gps_coordinates_required': photo_setting.gps_coordinates_required if photo_setting else True,
            },
            'fields': fields_data
        }

    @classmethod
    def save_form_from_dict(cls, activity, payload):
        """
        Saves form builder configuration atomically from a dictionary payload.
        Updates ActivityFormConfiguration, ActivityFormPhotoSetting, ActivityFormField,
        ActivityFormFieldOption, and ActivityFormValidationRule records.
        Also creates/updates the synchronized DynamicForm and links it to ActivityMaster.
        """
        with transaction.atomic():
            form_config = cls.get_or_create_form_config(activity)

            # 1. Update basic info
            form_config.form_title = payload.get('form_title', form_config.form_title).strip()
            form_config.description = payload.get('description', form_config.description)
            form_config.is_active = payload.get('is_active', True)
            form_config.save()

            # 2. Update Photo Settings
            photo_data = payload.get('photo_settings', {})
            photo_setting, _ = ActivityFormPhotoSetting.objects.get_or_create(form_config=form_config)
            photo_setting.enable_photo_capture = bool(photo_data.get('enable_photo_capture', False))
            photo_setting.before_photo_required = bool(photo_data.get('before_photo_required', False))
            photo_setting.after_photo_required = bool(photo_data.get('after_photo_required', False))
            photo_setting.optional_photo = bool(photo_data.get('optional_photo', True))
            photo_setting.photo_instructions = photo_data.get('photo_instructions', '').strip()
            photo_setting.capture_timestamp_required = bool(photo_data.get('capture_timestamp_required', True))
            photo_setting.submission_timestamp_required = bool(photo_data.get('submission_timestamp_required', True))
            photo_setting.gps_coordinates_required = bool(photo_data.get('gps_coordinates_required', True))
            photo_setting.save()

            # 3. Synchronize fields
            fields_data = payload.get('fields', [])
            existing_fields = {f.id: f for f in form_config.fields.all()}
            keep_field_ids = []

            for index, f_data in enumerate(fields_data):
                field_id = f_data.get('id')
                field = None
                if field_id is not None and str(field_id).isdigit():
                    num_id = int(field_id)
                    if num_id in existing_fields:
                        field = existing_fields[num_id]

                if field is None:
                    field = ActivityFormField(form_config=form_config)

                field.field_label = f_data.get('field_label', '').strip() or f"Field {index + 1}"
                field.field_type = f_data.get('field_type', 'short_text')
                field.placeholder = f_data.get('placeholder', '').strip()
                field.help_text = f_data.get('help_text', '').strip()
                field.is_required = bool(f_data.get('is_required', False))
                field.field_order = index + 1
                field.is_active = True
                field.settings = f_data.get('settings', {})
                field.save()
                keep_field_ids.append(field.id)

                # 3a. Save Options (for dropdown / multiple_choice)
                options_data = f_data.get('options', [])
                field.options.all().delete()
                for o_idx, opt in enumerate(options_data):
                    lbl = str(opt.get('label') or opt.get('value') or '').strip()
                    val = str(opt.get('value') or lbl).strip()
                    if lbl or val:
                        ActivityFormFieldOption.objects.create(
                            field=field,
                            option_label=lbl,
                            option_value=val,
                            display_order=o_idx + 1,
                            is_default=bool(opt.get('is_default', False))
                        )

                # 3b. Save Validation / Exception Rules
                rules_data = f_data.get('validation_rules', [])
                field.validation_rules.all().delete()
                for r_data in rules_data:
                    min_val = r_data.get('min_value')
                    max_val = r_data.get('max_value')
                    ActivityFormValidationRule.objects.create(
                        field=field,
                        rule_type=r_data.get('rule_type', 'normal'),
                        rule_name=r_data.get('rule_name', 'Rule').strip() or 'Rule',
                        condition_operator=r_data.get('condition_operator', 'equals'),
                        expected_value=str(r_data.get('expected_value', '')).strip(),
                        acceptable_values=r_data.get('acceptable_values', []) if isinstance(r_data.get('acceptable_values'), list) else [],
                        min_value=Decimal(str(min_val)) if min_val is not None and str(min_val) != '' else None,
                        max_value=Decimal(str(max_val)) if max_val is not None and str(max_val) != '' else None,
                        error_message=r_data.get('error_message', '').strip(),
                        is_active=bool(r_data.get('is_active', True))
                    )

            # Remove fields no longer in the payload
            form_config.fields.exclude(id__in=keep_field_ids).delete()

            # 4. Synchronize with DynamicForm model for ActivityMaster foreign key
            sync_dynamic_form = activity.form
            if not sync_dynamic_form:
                sync_dynamic_form = DynamicForm.objects.create(
                    company_id=activity.company_id,
                    form_name=form_config.form_title,
                    description=form_config.description,
                    project_ids=[],
                    form_schema=cls.build_dynamic_form_schema(form_config),
                    is_active=1
                )
                activity.form = sync_dynamic_form
            else:
                sync_dynamic_form.form_name = form_config.form_title
                sync_dynamic_form.description = form_config.description
                sync_dynamic_form.form_schema = cls.build_dynamic_form_schema(form_config)
                sync_dynamic_form.save()

            # Keep ActivityMaster photo_required flag synced
            activity.photo_required = photo_setting.enable_photo_capture
            activity.save(update_fields=['form', 'photo_required', 'updated_at'])

            return form_config

    @staticmethod
    def build_dynamic_form_schema(form_config):
        """
        Builds a compatible JSON schema representation for dynamic_forms consumers.
        """
        fields = form_config.fields.filter(is_active=True).order_by('field_order', 'id')
        rows = []
        for f in fields:
            rows.append({
                'id': f.id,
                'name': f.field_label,
                'type': f.field_type,
                'unit': f.settings.get('unit', '') if f.settings else '',
                'required': f.is_required,
                'placeholder': f.placeholder or '',
                'options': [opt.option_label for opt in f.options.all()]
            })

        return {
            'form_type': 'activity_form',
            'version': '2.0',
            'columns': ['Status / Reading', 'Remarks'],
            'sections': [
                {
                    'name': 'Activity Checklist Fields',
                    'rows': rows
                }
            ]
        }

    @staticmethod
    def evaluate_submission(fields_config, submitted_values):
        """
        Evaluates submitted values against normal validation rules and business exception rules.
        Distinguishes between:
        1. Validation Errors (missing mandatory inputs, invalid format) -> blocks submission
        2. Business Exceptions (valid value, but falls outside acceptable business parameters) ->
           clearly identified with warning/amber status, recorded for Exception Report.
           Valid values are NOT highlighted in red.
        """
        validation_errors = {}
        exceptions = []

        for field in fields_config:
            f_id = str(field.get('id', ''))
            f_label = field.get('field_label', f"Field #{f_id}")
            f_type = field.get('field_type', 'short_text')
            is_req = field.get('is_required', False)
            settings = field.get('settings', {})
            rules = field.get('validation_rules', [])

            val = submitted_values.get(f_id)
            val_str = str(val).strip() if val is not None else ''

            # --- 1. Standard Required Validation ---
            if is_req and not val_str:
                validation_errors[f_id] = f"{f_label} is required."
                continue

            # If empty and not required, skip further value validation
            if not val_str:
                continue

            # --- 2. Type Syntax Validation ---
            parsed_num = None
            if f_type == 'number':
                try:
                    parsed_num = float(val_str)
                except ValueError:
                    validation_errors[f_id] = f"{f_label} must be a valid numeric value."
                    continue

                min_limit = settings.get('min_value')
                max_limit = settings.get('max_value')
                if min_limit is not None and str(min_limit) != '' and parsed_num < float(min_limit):
                    validation_errors[f_id] = f"{f_label} cannot be less than {min_limit}."
                    continue
                if max_limit is not None and str(max_limit) != '' and parsed_num > float(max_limit):
                    validation_errors[f_id] = f"{f_label} cannot exceed {max_limit}."
                    continue

            elif f_type in ['short_text', 'long_text']:
                max_len = settings.get('max_length')
                min_len = settings.get('min_length')
                if max_len and len(val_str) > int(max_len):
                    validation_errors[f_id] = f"{f_label} exceeds maximum allowed length of {max_len} characters."
                    continue
                if min_len and len(val_str) < int(min_len):
                    validation_errors[f_id] = f"{f_label} must be at least {min_len} characters."
                    continue

            # --- 3. Business Exception Rules (Evaluated only when input syntax is valid) ---
            for rule in rules:
                if not rule.get('is_active', True):
                    continue

                rule_type = rule.get('rule_type', 'normal')
                op = rule.get('condition_operator', 'equals')
                exp_val = str(rule.get('expected_value', '')).strip()
                acceptable_list = rule.get('acceptable_values', [])
                rule_min = rule.get('min_value')
                rule_max = rule.get('max_value')
                err_msg = rule.get('error_message', '').strip()

                is_exception = False
                expected_desc = ""

                # Yes/No Field Exception Check
                if f_type == 'yes_no':
                    if exp_val:
                        expected_desc = f"Expected: {exp_val}"
                        if val_str.lower() != exp_val.lower():
                            is_exception = True

                # Number Field Exception Check
                elif f_type == 'number' and parsed_num is not None:
                    if op == 'between' and (rule_min is not None or rule_max is not None):
                        min_ok = True if rule_min is None else (parsed_num >= float(rule_min))
                        max_ok = True if rule_max is None else (parsed_num <= float(rule_max))
                        expected_desc = f"Acceptable: {rule_min if rule_min is not None else '-inf'} to {rule_max if rule_max is not None else '+inf'}"
                        if not (min_ok and max_ok):
                            is_exception = True
                    elif op in ['gte', 'min'] and rule_min is not None:
                        expected_desc = f"Acceptable: >= {rule_min}"
                        if parsed_num < float(rule_min):
                            is_exception = True
                    elif op in ['lte', 'max'] and rule_max is not None:
                        expected_desc = f"Acceptable: <= {rule_max}"
                        if parsed_num > float(rule_max):
                            is_exception = True
                    elif op == 'equals' and exp_val:
                        expected_desc = f"Acceptable: {exp_val}"
                        try:
                            if parsed_num != float(exp_val):
                                is_exception = True
                        except ValueError:
                            pass

                # Dropdown / Multiple Choice Exception Check
                elif f_type in ['dropdown', 'multiple_choice']:
                    if acceptable_list and len(acceptable_list) > 0:
                        expected_desc = f"Acceptable choices: {', '.join(acceptable_list)}"
                        if val_str not in acceptable_list:
                            is_exception = True
                    elif exp_val:
                        expected_desc = f"Expected: {exp_val}"
                        if val_str.lower() != exp_val.lower():
                            is_exception = True

                # Text Exception Check
                elif f_type in ['short_text', 'long_text']:
                    if exp_val and val_str.lower() != exp_val.lower():
                        expected_desc = f"Expected: {exp_val}"
                        is_exception = True

                # Record Exception or Validation Error
                if is_exception:
                    msg = err_msg or f"{f_label} value '{val_str}' deviates from standard operating parameter ({expected_desc})."
                    if rule_type == 'business_exception':
                        exceptions.append({
                            'field_id': f_id,
                            'field_label': f_label,
                            'submitted_value': val_str,
                            'expected_value': expected_desc,
                            'rule_name': rule.get('rule_name', 'Operational Exception'),
                            'message': msg,
                            'severity': 'Warning' if 'warning' in msg.lower() else 'Critical',
                            'timestamp': timezone.now().strftime('%d %b %Y, %I:%M %p')
                        })
                    else:
                        validation_errors[f_id] = msg

        return {
            'is_valid': len(validation_errors) == 0,
            'validation_errors': validation_errors,
            'has_exceptions': len(exceptions) > 0,
            'exceptions': exceptions
        }

    @staticmethod
    def get_prebuilt_templates():
        """
        Industry solar pre-built templates for Battery Check,
        Solar Panel Cleaning, and Inverter Inspection.
        """
        return {
            'battery_check': {
                'form_title': 'Battery Bank Inspection & Voltage Checklist',
                'description': 'Comprehensive battery cell condition, voltage, temperature, and specific gravity verification.',
                'photo_settings': {
                    'enable_photo_capture': True,
                    'before_photo_required': True,
                    'after_photo_required': True,
                    'optional_photo': False,
                    'photo_instructions': 'Take a clear direct photo of the battery bank terminals before and after testing.',
                    'capture_timestamp_required': True,
                    'submission_timestamp_required': True,
                    'gps_coordinates_required': True
                },
                'fields': [
                    {
                        'field_label': 'Battery Condition',
                        'field_type': 'yes_no',
                        'placeholder': '',
                        'help_text': 'Confirm physical integrity without swelling, leaks, or acid deposits.',
                        'is_required': True,
                        'field_order': 1,
                        'settings': {},
                        'options': [],
                        'validation_rules': [
                            {
                                'rule_type': 'business_exception',
                                'rule_name': 'Physical Condition Check',
                                'condition_operator': 'equals',
                                'expected_value': 'Yes',
                                'error_message': 'Battery condition marked abnormal: Swelling or acid deposit detected.'
                            }
                        ]
                    },
                    {
                        'field_label': 'Battery Voltage',
                        'field_type': 'number',
                        'placeholder': 'Enter voltage in Volts (e.g. 12.6)',
                        'help_text': 'Nominal reading range: 8.0V - 14.5V per bank.',
                        'is_required': True,
                        'field_order': 2,
                        'settings': {'unit': 'V', 'min_value': 0, 'max_value': 30, 'step': '0.1'},
                        'options': [],
                        'validation_rules': [
                            {
                                'rule_type': 'business_exception',
                                'rule_name': 'Voltage Operating Window',
                                'condition_operator': 'between',
                                'min_value': 8.0,
                                'max_value': 14.5,
                                'error_message': 'Battery Voltage is out of normal operational bounds (8.0V - 14.5V).'
                            }
                        ]
                    },
                    {
                        'field_label': 'Battery Temperature',
                        'field_type': 'number',
                        'placeholder': 'Enter cell surface temp in °C',
                        'help_text': 'Must not exceed 45°C during high float charging.',
                        'is_required': True,
                        'field_order': 3,
                        'settings': {'unit': '°C', 'min_value': -10, 'max_value': 90, 'step': '0.5'},
                        'options': [],
                        'validation_rules': [
                            {
                                'rule_type': 'business_exception',
                                'rule_name': 'Thermal Limit',
                                'condition_operator': 'lte',
                                'max_value': 45.0,
                                'error_message': 'High thermal hazard: Battery temperature exceeds 45°C!'
                            }
                        ]
                    },
                    {
                        'field_label': 'Electrolyte Level',
                        'field_type': 'dropdown',
                        'placeholder': 'Select current electrolyte status',
                        'help_text': 'Applicable to flooded lead-acid batteries.',
                        'is_required': True,
                        'field_order': 4,
                        'settings': {},
                        'options': [
                            {'label': 'Optimal (Green Line)', 'value': 'Optimal', 'display_order': 1},
                            {'label': 'Low - Needs Demineralized Water', 'value': 'Low', 'display_order': 2},
                            {'label': 'Critical Dry Plates', 'value': 'Critical Dry', 'display_order': 3}
                        ],
                        'validation_rules': [
                            {
                                'rule_type': 'business_exception',
                                'rule_name': 'Electrolyte Sufficiency',
                                'condition_operator': 'equals',
                                'acceptable_values': ['Optimal'],
                                'error_message': 'Low electrolyte level detected. Demineralized water top-up required.'
                            }
                        ]
                    },
                    {
                        'field_label': 'Terminal Corrosion Inspection',
                        'field_type': 'yes_no',
                        'placeholder': '',
                        'help_text': 'Is terminal free of sulfation/corrosion?',
                        'is_required': True,
                        'field_order': 5,
                        'settings': {},
                        'options': [],
                        'validation_rules': [
                            {
                                'rule_type': 'business_exception',
                                'rule_name': 'Corrosion Check',
                                'condition_operator': 'equals',
                                'expected_value': 'Yes',
                                'error_message': 'Corrosion or sulfate crystallization observed on battery terminals.'
                            }
                        ]
                    },
                    {
                        'field_label': 'Maintenance Remarks & Observations',
                        'field_type': 'long_text',
                        'placeholder': 'Record any noticeable cell defects, torque tightening, or action items...',
                        'help_text': 'Detailed notes for site engineers.',
                        'is_required': False,
                        'field_order': 6,
                        'settings': {'max_length': 1000},
                        'options': [],
                        'validation_rules': []
                    }
                ]
            },
            'solar_panel_cleaning': {
                'form_title': 'Solar PV Module Cleaning Quality Checklist',
                'description': 'Pre and post cleaning quality inspection, module surface cleanliness, and shading verification.',
                'photo_settings': {
                    'enable_photo_capture': True,
                    'before_photo_required': True,
                    'after_photo_required': True,
                    'optional_photo': False,
                    'photo_instructions': 'Capture high-resolution before and after photos showing module array cleanliness.',
                    'capture_timestamp_required': True,
                    'submission_timestamp_required': True,
                    'gps_coordinates_required': True
                },
                'fields': [
                    {
                        'field_label': 'Initial Panel Condition',
                        'field_type': 'dropdown',
                        'placeholder': 'Select soiling state before cleaning',
                        'help_text': 'Categorize the array soiling level.',
                        'is_required': True,
                        'field_order': 1,
                        'settings': {},
                        'options': [
                            {'label': 'Light Dust', 'value': 'Light Dust', 'display_order': 1},
                            {'label': 'Moderate Soiling', 'value': 'Moderate Soiling', 'display_order': 2},
                            {'label': 'Heavy Soiling / Bird Droppings', 'value': 'Heavy Soiling', 'display_order': 3},
                            {'label': 'Industrial Film / Cement Dust', 'value': 'Industrial Dust', 'display_order': 4}
                        ],
                        'validation_rules': []
                    },
                    {
                        'field_label': 'Cleaning Status',
                        'field_type': 'yes_no',
                        'placeholder': '',
                        'help_text': 'Was array cleaned completely to scratch-free standard?',
                        'is_required': True,
                        'field_order': 2,
                        'settings': {},
                        'options': [],
                        'validation_rules': [
                            {
                                'rule_type': 'business_exception',
                                'rule_name': 'Cleaning Completion',
                                'condition_operator': 'equals',
                                'expected_value': 'Yes',
                                'error_message': 'Cleaning marked incomplete or unsatisfied.'
                            }
                        ]
                    },
                    {
                        'field_label': 'Modules Cleaned (Nos)',
                        'field_type': 'number',
                        'placeholder': 'Total number of panels cleaned',
                        'help_text': 'Quantity of solar modules washed in this task.',
                        'is_required': True,
                        'field_order': 3,
                        'settings': {'unit': 'Nos', 'min_value': 1, 'max_value': 5000, 'step': '1'},
                        'options': [],
                        'validation_rules': []
                    },
                    {
                        'field_label': 'Water Source Used',
                        'field_type': 'dropdown',
                        'placeholder': 'Select water purification source',
                        'help_text': 'TDS < 200 ppm recommended.',
                        'is_required': True,
                        'field_order': 4,
                        'settings': {},
                        'options': [
                            {'label': 'Demineralized (DM) Water', 'value': 'DM Water', 'display_order': 1},
                            {'label': 'RO Filtered Water', 'value': 'RO Water', 'display_order': 2},
                            {'label': 'Borewell / Tap Water (High TDS)', 'value': 'Borewell Water', 'display_order': 3}
                        ],
                        'validation_rules': [
                            {
                                'rule_type': 'business_exception',
                                'rule_name': 'Water Quality Standard',
                                'condition_operator': 'equals',
                                'acceptable_values': ['DM Water', 'RO Water'],
                                'error_message': 'High TDS / Borewell water used! May cause scale buildup on tempered glass.'
                            }
                        ]
                    },
                    {
                        'field_label': 'Micro-cracks or Glass Breakage Observed',
                        'field_type': 'yes_no',
                        'placeholder': '',
                        'help_text': 'Are all modules structurally intact without cracks?',
                        'is_required': True,
                        'field_order': 5,
                        'settings': {},
                        'options': [],
                        'validation_rules': [
                            {
                                'rule_type': 'business_exception',
                                'rule_name': 'Structural Glass Integrity',
                                'condition_operator': 'equals',
                                'expected_value': 'No',
                                'error_message': 'Module glass damage or micro-cracks reported during cleaning.'
                            }
                        ]
                    },
                    {
                        'field_label': 'Inspection Remarks',
                        'field_type': 'long_text',
                        'placeholder': 'Remarks on wiper quality, tilt angles, or water drainage...',
                        'help_text': 'Optional feedback.',
                        'is_required': False,
                        'field_order': 6,
                        'settings': {'max_length': 1000},
                        'options': [],
                        'validation_rules': []
                    }
                ]
            },
            'inverter_inspection': {
                'form_title': 'Central / String Inverter Operational Checklist',
                'description': 'Inverter AC/DC electrical parameters, heatsink thermal status, and display error codes check.',
                'photo_settings': {
                    'enable_photo_capture': True,
                    'before_photo_required': True,
                    'after_photo_required': False,
                    'optional_photo': True,
                    'photo_instructions': 'Capture live photograph of inverter LCD display screen showing active power reading.',
                    'capture_timestamp_required': True,
                    'submission_timestamp_required': True,
                    'gps_coordinates_required': True
                },
                'fields': [
                    {
                        'field_label': 'Inverter Display Operating State',
                        'field_type': 'dropdown',
                        'placeholder': 'Select current operational state',
                        'help_text': 'As reported on LCD / LED indicator.',
                        'is_required': True,
                        'field_order': 1,
                        'settings': {},
                        'options': [
                            {'label': 'Normal Generating (MPPT Active)', 'value': 'Normal Generating', 'display_order': 1},
                            {'label': 'Derating (Thermal / Grid Limit)', 'value': 'Derating', 'display_order': 2},
                            {'label': 'Fault / Alarm Shutdown', 'value': 'Fault Shutdown', 'display_order': 3},
                            {'label': 'Standby / Low Radiation', 'value': 'Standby', 'display_order': 4}
                        ],
                        'validation_rules': [
                            {
                                'rule_type': 'business_exception',
                                'rule_name': 'Inverter State Check',
                                'condition_operator': 'equals',
                                'acceptable_values': ['Normal Generating', 'Standby'],
                                'error_message': 'Inverter is in abnormal Derating or Fault state!'
                            }
                        ]
                    },
                    {
                        'field_label': 'Grid AC Voltage (Phase-to-Phase)',
                        'field_type': 'number',
                        'placeholder': 'Enter nominal AC voltage (e.g. 415)',
                        'help_text': 'Acceptable operating band: 380V - 440V',
                        'is_required': True,
                        'field_order': 2,
                        'settings': {'unit': 'V', 'min_value': 200, 'max_value': 600, 'step': '1'},
                        'options': [],
                        'validation_rules': [
                            {
                                'rule_type': 'business_exception',
                                'rule_name': 'AC Grid Voltage Tolerance',
                                'condition_operator': 'between',
                                'min_value': 380.0,
                                'max_value': 440.0,
                                'error_message': 'AC Grid voltage deviates beyond acceptable threshold (380V - 440V).'
                            }
                        ]
                    },
                    {
                        'field_label': 'DC Bus Voltage',
                        'field_type': 'number',
                        'placeholder': 'Enter DC voltage (e.g. 680)',
                        'help_text': 'Typical MPPT range: 550V - 850V',
                        'is_required': True,
                        'field_order': 3,
                        'settings': {'unit': 'V', 'min_value': 0, 'max_value': 1500, 'step': '1'},
                        'options': [],
                        'validation_rules': [
                            {
                                'rule_type': 'business_exception',
                                'rule_name': 'DC Voltage Window',
                                'condition_operator': 'between',
                                'min_value': 550.0,
                                'max_value': 850.0,
                                'error_message': 'DC Bus voltage is out of optimum MPPT generation range.'
                            }
                        ]
                    },
                    {
                        'field_label': 'Cooling Fans Operational',
                        'field_type': 'yes_no',
                        'placeholder': '',
                        'help_text': 'Are internal/external exhaust fans spinning freely without vibration?',
                        'is_required': True,
                        'field_order': 4,
                        'settings': {},
                        'options': [],
                        'validation_rules': [
                            {
                                'rule_type': 'business_exception',
                                'rule_name': 'Fan Operability',
                                'condition_operator': 'equals',
                                'expected_value': 'Yes',
                                'error_message': 'Inverter cooling fan failure reported. Risk of thermal shutdown.'
                            }
                        ]
                    },
                    {
                        'field_label': 'Heatsink Internal Temperature',
                        'field_type': 'number',
                        'placeholder': 'Enter heatsink temp in °C',
                        'help_text': 'Thermal derating begins above 65°C.',
                        'is_required': True,
                        'field_order': 5,
                        'settings': {'unit': '°C', 'min_value': 0, 'max_value': 120, 'step': '1'},
                        'options': [],
                        'validation_rules': [
                            {
                                'rule_type': 'business_exception',
                                'rule_name': 'Heatsink Thermal Limit',
                                'condition_operator': 'lte',
                                'max_value': 65.0,
                                'error_message': 'Inverter heatsink temperature exceeds 65°C threshold!'
                            }
                        ]
                    },
                    {
                        'field_label': 'Active Alarm Codes or Remarks',
                        'field_type': 'long_text',
                        'placeholder': 'Log any active warning codes (e.g. E023, Grid Overvoltage)...',
                        'help_text': 'Leave blank if clear.',
                        'is_required': False,
                        'field_order': 6,
                        'settings': {'max_length': 1000},
                        'options': [],
                        'validation_rules': []
                    }
                ]
            }
        }
