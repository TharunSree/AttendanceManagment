# This list will be automatically populated by the @nav_item decorator
# as Django loads each of your app's views.py files.
REGISTERED_NAV_ITEMS = []

# The definition of the collapsible groups still lives here.
NAVIGATION_GROUPS = [
    {
        'id': 'dashboard',
        'title': 'Dashboard',
        'icon': 'iconsminds-shop-4',
    },
    {
        'id': 'admin_management',
        'title': 'Admin Management',
        'icon': 'iconsminds-gears',
    },
    {
        'id': 'faculty_tools',
        'title': 'Faculty Tools',
        'icon': 'iconsminds-check',
        'role_required': 'faculty',  # Only visible to faculty
    },
    {
        'id': 'application_settings',  # Unique ID for the group
        'title': 'Application Settings',
        'icon': 'iconsminds-gears',
    },
    {
        'id': 'my_academics',
        'title': 'My Academics',
        'icon': 'simple-icon-user',
        'role_required': 'student',  # Only visible to students
    }
]

SUBGROUP_DEFINITIONS = {
    'academic_setup': {
        'title': 'Academic Setup',
        'icon': 'simple-icon-wrench',  # You can change this icon
        'order': 10
    },
    'user_management': {
        'title': 'User Management',
        'icon': 'simple-icon-people',  # You can change this icon
        'order': 20
    },
    'reporting': {
        'title': 'Reports & Logs',
        'icon': 'simple-icon-printer',  # You can change this icon
        'order': 30
    }
}

# 2. Map specific views to a subgroup
# This is where you assign items to a collapsible section.
# Key: The 'url_name' from the @nav_item decorator in your views.
# Value: The subgroup ID from SUBGROUP_DEFINITIONS above.
SUBGROUP_MAPPING = {
    # Subgroup: 'academic_setup'
    'academics:course_list': 'academic_setup',
    'academics:subject_list': 'academic_setup',
    'academics:manage_timetable': 'academic_setup',
    'academics:scheme_list': 'academic_setup',
    'academics:admin_settings': 'academic_setup',

    # Subgroup: 'user_management'
    'academics:admin_select_class': 'user_management',
    'academics:manage_substitutions': 'user_management',
    'academics:extra_class_list': 'user_management',

    # Subgroup: 'reporting'
    'academics:daily_log': 'reporting',
    'academics:late_comers': 'reporting',
    'academics:attendance_report': 'reporting',
    'academics:marks_report': 'reporting',
}
