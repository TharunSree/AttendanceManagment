# This list will be automatically populated by the @nav_item decorator
# when Django starts and imports your views.py files.
REGISTERED_NAV_ITEMS = []

# We still define the groups manually, as this is the clearest way to manage them.
NAVIGATION_GROUPS = [
    {
        'id': 'admin_management',
        'title': 'Admin Management',
        'icon': 'iconsminds-gears',
        'roles': ['admin'],
    },
    {
        'id': 'attendance_views',
        'title': 'Attendance',
        'icon': 'iconsminds-pie-chart-3',
        'roles': ['admin'],
    },
    {
        'id': 'mark_attendance',
        'title': 'Mark Attendance',
        'icon': 'iconsminds-check',
        'roles': ['faculty'],
    }
]